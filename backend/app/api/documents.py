import uuid

from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)

from fastapi.responses import (
    FileResponse,
)

from datetime import date, datetime, time, timedelta

from sqlalchemy import func, or_, select

from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_user,
    get_current_admin
)

from app.db.session import get_db

from app.models.document import Document

from app.models.document_ai_result import (
    DocumentAIResult,
)

from app.models.document_extraction import (
    DocumentExtraction,
)

from app.models.hospitalization import (
    Hospitalization,
)

from app.models.patient import Patient

from app.models.service import Service

from app.models.user import User

from app.schemas.document import (
    ArchivedDocumentResponse,
    DocumentResponse,
)

from app.schemas.document_verification import (
    DocumentVerificationRequest,
)

from app.services.document_identification_service import (
    identify_document,
)

from app.tasks.document_tasks import (
    process_document,
)

from app.services.audit_service import create_audit_log


router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)


STORAGE_DIR = Path(
    "storage/documents"
)

STORAGE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# UPLOAD
# ============================================================

@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):

    if file.content_type != (
        "application/pdf"
    ):

        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed",
        )

    document_id = uuid.uuid4()

    stored_filename = (
        f"{document_id}.pdf"
    )

    file_path = (
        STORAGE_DIR / stored_filename
    )

    try:

        with file_path.open(
            "wb"
        ) as buffer:

            while chunk := await file.read(
                1024 * 1024
            ):

                buffer.write(chunk)

    except Exception:

        if file_path.exists():
            file_path.unlink()

        raise HTTPException(
            status_code=500,
            detail="Failed to store document",
        )

    document = Document(
        id=document_id,

        hospitalization_id=None,

        original_filename=(
            file.filename
            or "document.pdf"
        ),

        stored_filename=stored_filename,

        storage_path=str(
            file_path
        ),

        status="IMPORTED",
    )

    try:

        db.add(document)

        create_audit_log(
        db,
        user=current_user,
        action="document importe",
        entity_type="DOCUMENT",
        entity_id=document.id,
        description=(
        f"'{current_user.username}' "
        f"a importé le document "
        f"'{document.original_filename}'."
    ),
        details={
        "filename": document.original_filename,
    },
    )

        db.commit()

        db.refresh(document)

    except Exception:

        db.rollback()

        if file_path.exists():
            file_path.unlink()

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to create document record"
            ),
        )

    # ========================================================
    # BACKGROUND JOB
    # ========================================================

    try:

        process_document.delay(
            str(document.id)
        )

    except Exception:

        document.status = (
            "PROCESSING_ERROR"
        )

        db.commit()

        raise HTTPException(
            status_code=503,
            detail=(
                "Document was saved but "
                "background processing "
                "could not be started"
            ),
        )

    return document


# ============================================================
# LIST DOCUMENTS
# ============================================================


@router.get(
    "",
    response_model=list[DocumentResponse],
)
def get_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):

    return db.scalars(
        select(Document)
        .order_by(
            Document.created_at.desc()
        )
    ).all()




# =======================
# SEARCH FOR DOCS
# ====================


@router.get("/archived")
def search_archived_documents(
    date_filter: date | None = Query(
        default=None,
        alias="date",
    ),
    month: str | None = Query(
        default=None,
        description="YYYY-MM",
    ),
    year: int | None = Query(
        default=None,
        ge=2000,
        le=2100,
    ),
    last_days: int | None = Query(
        default=None,
        ge=1,
        le=3650,
    ),
    last_months: int | None = Query(
        default=None,
        ge=1,
        le=120,
    ),
    q: str | None = Query(
        default=None,
        min_length=1,
    ),
    hospitalization_number: str | None = Query(
        default=None,
        min_length=1,
    ),
    cni: str | None = Query(
        default=None,
        min_length=1,
    ),
    first_name: str | None = Query(
        default=None,
        min_length=1,
    ),
    last_name: str | None = Query(
        default=None,
        min_length=1,
    ),
    service_id: uuid.UUID | None = Query(
        default=None,
    ),
    page: int = Query(
        default=1,
        ge=1,
    ),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    db: Session = Depends(get_db),
    #current_user: User = Depends(get_current_user),
):
    # --------------------------------------------------------
    # Only one date mode at a time
    # --------------------------------------------------------

    date_filters = [
        date_filter,
        month,
        year,
        last_days,
        last_months,
    ]

    if sum(
        value is not None
        for value in date_filters
    ) > 1:
        raise HTTPException(
            status_code=400,
            detail=(
                "Use only one of: "
                "date, month, year, "
                "last_days, last_months"
            ),
        )

    # --------------------------------------------------------
    # Base query
    # --------------------------------------------------------

    query = (
        select(
            Document,
            Hospitalization,
            Patient,
            Service,
        )
        .join(
            Hospitalization,
            Document.hospitalization_id
            == Hospitalization.id,
        )
        .join(
            Patient,
            Hospitalization.patient_id
            == Patient.id,
        )
        .join(
            Service,
            Hospitalization.service_id
            == Service.id,
        )
        .where(
            Document.status == "ARCHIVED",
            Document.archived_at.is_not(None),
        )
    )

    # --------------------------------------------------------
    # Date filtering
    # --------------------------------------------------------

    start_datetime: datetime | None = None
    end_datetime: datetime | None = None

    # Exact day
    if date_filter is not None:
        start_datetime = datetime.combine(
            date_filter,
            time.min,
        )

        end_datetime = (
            start_datetime
            + timedelta(days=1)
        )

    # Month: YYYY-MM
    elif month is not None:
        try:
            month_date = datetime.strptime(
                month,
                "%Y-%m",
            ).date()
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid month. "
                    "Expected YYYY-MM."
                ),
            )

        start_datetime = datetime(
            month_date.year,
            month_date.month,
            1,
        )

        if month_date.month == 12:
            end_datetime = datetime(
                month_date.year + 1,
                1,
                1,
            )
        else:
            end_datetime = datetime(
                month_date.year,
                month_date.month + 1,
                1,
            )

    # Year
    elif year is not None:
        start_datetime = datetime(
            year,
            1,
            1,
        )

        end_datetime = datetime(
            year + 1,
            1,
            1,
        )

    # Last N days
    elif last_days is not None:
        end_datetime = datetime.utcnow()

        start_datetime = (
            end_datetime
            - timedelta(days=last_days)
        )

    # Last N calendar months
    elif last_months is not None:
        end_datetime = datetime.utcnow()

        total_months = (
            end_datetime.year * 12
            + end_datetime.month
            - 1
            - last_months
        )

        start_year = total_months // 12
        start_month = (
            total_months % 12
        ) + 1

        start_datetime = datetime(
            start_year,
            start_month,
            1,
        )

    if start_datetime is not None:
        query = query.where(
            Document.archived_at
            >= start_datetime
        )

    if end_datetime is not None:
        query = query.where(
            Document.archived_at
            < end_datetime
        )

    # --------------------------------------------------------
    # General search
    #
    # q=Ahmed
    #
    # searches:
    # - CNI
    # - first name
    # - last name
    # - hospitalization number
    # --------------------------------------------------------

    if q is not None:
        value = q.strip()

        if value:
            pattern = f"%{value}%"

            query = query.where(
                or_(
                    Patient.cni.ilike(pattern),
                    Patient.first_name.ilike(
                        pattern
                    ),
                    Patient.last_name.ilike(
                        pattern
                    ),
                    Hospitalization
                    .hospitalization_number
                    .ilike(pattern),
                )
            )

    # --------------------------------------------------------
    # Exact hospitalization number
    # --------------------------------------------------------

    if hospitalization_number is not None:
        value = hospitalization_number.strip()

        if value:
            query = query.where(
                Hospitalization
                .hospitalization_number
                == value
            )

    # --------------------------------------------------------
    # Exact CNI
    # --------------------------------------------------------

    if cni is not None:
        value = cni.strip()

        if value:
            query = query.where(
                Patient.cni == value
            )

    # --------------------------------------------------------
    # First name
    # --------------------------------------------------------

    if first_name is not None:
        value = first_name.strip()

        if value:
            query = query.where(
                Patient.first_name.ilike(
                    f"%{value}%"
                )
            )

    # --------------------------------------------------------
    # Last name
    # --------------------------------------------------------

    if last_name is not None:
        value = last_name.strip()

        if value:
            query = query.where(
                Patient.last_name.ilike(
                    f"%{value}%"
                )
            )

    # --------------------------------------------------------
    # Service
    # --------------------------------------------------------

    if service_id is not None:
        query = query.where(
            Service.id == service_id
        )

    # --------------------------------------------------------
    # Count BEFORE pagination
    # --------------------------------------------------------

    count_query = select(
        func.count()
    ).select_from(
        query.subquery()
    )

    total = db.scalar(
        count_query
    ) or 0

    # --------------------------------------------------------
    # Pagination
    # --------------------------------------------------------

    offset = (
        page - 1
    ) * page_size

    query = (
        query
        .order_by(
            Document.archived_at.desc(),
            Document.id.desc(),
        )
        .offset(offset)
        .limit(page_size)
    )

    rows = db.execute(query).all()

    # --------------------------------------------------------
    # Response
    # --------------------------------------------------------

    items = []

    for (
        document,
        hospitalization,
        patient,
        service,
    ) in rows:

        items.append(
            {
                "id": str(document.id),

                "original_filename": (
                    document.original_filename
                ),

                "status": document.status,

                "created_at": (
                    document.created_at.isoformat()
                ),

                "archived_at": (
                    document.archived_at.isoformat()
                    if document.archived_at
                    else None
                ),

                "patient": {
                    "id": str(patient.id),
                    "cni": patient.cni,
                    "first_name": (
                        patient.first_name
                    ),
                    "last_name": (
                        patient.last_name
                    ),
                },

                "hospitalization": {
                    "id": str(
                        hospitalization.id
                    ),
                    "number": (
                        hospitalization
                        .hospitalization_number
                    ),
                    "admission_date": (
                        hospitalization
                        .admission_date
                        .isoformat()
                        if hospitalization.admission_date
                        else None
                    ),
                    "discharge_date": (
                        hospitalization
                        .discharge_date
                        .isoformat()
                        if hospitalization.discharge_date
                        else None
                    ),
                },

                "service": {
                    "id": str(service.id),
                    "name": service.name,
                    "is_active": (
                        service.is_active
                    ),
                },
            }
        )

    total_pages = (
        (total + page_size - 1)
        // page_size
        if total
        else 0
    )

    return {
        "items": items,

        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        },
    }


# ============================================================
# ARCHIVED DOCUMENT DETAILS
# ============================================================

@router.get(
    "/{document_id}",
    response_model=ArchivedDocumentResponse,
)
def get_archived_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = db.get(Document, document_id)

    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    if document.status != "ARCHIVED":
        raise HTTPException(status_code=400, detail="Document is not archived")

    row = db.execute(
        select(Hospitalization, Patient, Service)
        .join(Patient, Hospitalization.patient_id == Patient.id)
        .join(Service, Hospitalization.service_id == Service.id)
        .where(Hospitalization.id == document.hospitalization_id)
    ).one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail="Archived document data not found")

    hospitalization, patient, service = row
    return {
        "id": document.id,
        "original_filename": document.original_filename,
        "status": document.status,
        "created_at": document.created_at,
        "archived_at": document.archived_at,
        "patient": {
            "id": patient.id,
            "cni": patient.cni,
            "first_name": patient.first_name,
            "last_name": patient.last_name,
        },
        "hospitalization": {
            "id": hospitalization.id,
            "number": hospitalization.hospitalization_number,
            "admission_date": hospitalization.admission_date,
            "discharge_date": hospitalization.discharge_date,
        },
        "service": {
            "id": service.id,
            "name": service.name,
            "is_active": service.is_active,
        },
    }





# ============================================================
# STATUS
# ============================================================

@router.get(
    "/{document_id}/status",
)
def get_document_status(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):

    document = db.get(
        Document,
        document_id,
    )

    if document is None:

        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    return {
        "document_id": str(
            document.id
        ),
        "status": document.status,
    }


# ============================================================
# PDF
# ============================================================

@router.get(
    "/{document_id}/file",
)
def get_document_file(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):

    document = db.get(
        Document,
        document_id,
    )

    if document is None:

        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    file_path = Path(
        document.storage_path
    )

    if not file_path.exists():

        raise HTTPException(
            status_code=404,
            detail="Document file not found",
        )

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=document.original_filename,
    )


# ============================================================
# REVIEW
# ============================================================

@router.get(
    "/{document_id}/review",
)
def review_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):

    document = db.get(
        Document,
        document_id,
    )

    if document is None:

        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    if document.status != (
        "READY_FOR_REVIEW"
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Document is not ready "
                "for review"
            ),
        )

    ai_result = db.scalar(
        select(DocumentAIResult).where(
            DocumentAIResult.document_id
            == document.id
        )
    )

    if ai_result is None:

        raise HTTPException(
            status_code=400,
            detail=(
                "AI analysis has not been completed"
            ),
        )

    identification = identify_document(
        db=db,

        cni=ai_result.cni,

        first_name=ai_result.first_name,

        last_name=ai_result.last_name,

        hospitalization_number=(
            ai_result.hospitalization_number
        ),

        service_name=(
            ai_result.service_name
        ),
    )

    patient = identification[
        "patient"
    ]["patient"]

    hospitalization = identification[
        "hospitalization"
    ]["hospitalization"]

    service = identification[
        "service"
    ]["service"]

    return {

        "document": {
            "id": str(document.id),

            "filename": (
                document.original_filename
            ),

            "status": document.status,
        },

        "ai": {

            "cni": ai_result.cni,

            "first_name": (
                ai_result.first_name
            ),

            "last_name": (
                ai_result.last_name
            ),

            "hospitalization_number": (
                ai_result
                .hospitalization_number
            ),

            "service_name": (
                ai_result.service_name
            ),

            "admission_date": (
                ai_result
                .admission_date
                .isoformat()
                if ai_result.admission_date
                else None
            ),

            "discharge_date": (
                ai_result
                .discharge_date
                .isoformat()
                if ai_result.discharge_date
                else None
            ),
        },

        "identification": {

            "patient": {
                "status": (
                    identification[
                        "patient"
                    ]["status"]
                ),

                "id": (
                    str(patient.id)
                    if patient
                    else None
                ),
            },

            "hospitalization": {
                "status": (
                    identification[
                        "hospitalization"
                    ]["status"]
                ),

                "id": (
                    str(hospitalization.id)
                    if hospitalization
                    else None
                ),
            },

            "service": {
                "status": (
                    identification[
                        "service"
                    ]["status"]
                ),

                "id": (
                    str(service.id)
                    if service
                    else None
                ),
            },
        },
    }


# ============================================================
# VERIFY + ARCHIVE
# ============================================================

@router.post(
    "/{document_id}/verify",
)
def verify_document(
    document_id: uuid.UUID,
    payload: DocumentVerificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):

    document = db.get(
        Document,
        document_id,
    )

    if document is None:

        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    if document.status != (
        "READY_FOR_REVIEW"
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Document is not ready "
                "for verification"
            ),
        )

    if (
        payload.discharge_date
        and payload.discharge_date
        < payload.admission_date
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Discharge date cannot be "
                "before admission date"
            ),
        )

    try:

        # ====================================================
        # SERVICE
        # ====================================================

        try:

            service_uuid = uuid.UUID(
                payload.service_id
            )

        except ValueError:

            raise HTTPException(
                status_code=400,
                detail="Invalid service ID",
            )

        service = db.get(
            Service,
            service_uuid,
        )

        if service is None:

            raise HTTPException(
                status_code=400,
                detail="Service not found",
            )

        if not service.is_active:

            raise HTTPException(
                status_code=400,
                detail="Service is inactive",
            )

        # ====================================================
        # PATIENT
        # ====================================================

        patient = db.scalar(
            select(Patient).where(
                Patient.cni
                == payload.cni
            )
        )

        if patient:

            names_match = (
                patient.first_name
                .strip()
                .lower()
                ==
                payload.first_name
                .strip()
                .lower()
                and
                patient.last_name
                .strip()
                .lower()
                ==
                payload.last_name
                .strip()
                .lower()
            )

            if not names_match:

                raise HTTPException(
                    status_code=409,
                    detail=(
                        "Patient CNI exists, "
                        "but patient name does "
                        "not match"
                    ),
                )

        else:

            patient = Patient(
                cni=payload.cni.strip(),

                first_name=(
                    payload.first_name.strip()
                ),

                last_name=(
                    payload.last_name.strip()
                ),
            )

            db.add(patient)

            db.flush()

        # ====================================================
        # HOSPITALIZATION
        # ====================================================

        hospitalization = db.scalar(
            select(Hospitalization).where(
                Hospitalization
                .hospitalization_number
                ==
                payload
                .hospitalization_number
                .strip()
            )
        )

        if hospitalization:

            if (
                hospitalization.patient_id
                != patient.id
            ):

                raise HTTPException(
                    status_code=409,
                    detail=(
                        "This hospitalization "
                        "number belongs to "
                        "another patient"
                    ),
                )

            if (
                hospitalization.service_id
                != service.id
            ):

                raise HTTPException(
                    status_code=409,
                    detail=(
                        "This hospitalization "
                        "number belongs to "
                        "another service"
                    ),
                )

            existing_document = db.scalar(
                select(Document).where(
                    Document.hospitalization_id
                    == hospitalization.id
                )
            )

            if existing_document:

                raise HTTPException(
                    status_code=409,
                    detail=(
                        "This hospitalization "
                        "already has an archived "
                        "document"
                    ),
                )

        else:

            hospitalization = Hospitalization(

                hospitalization_number=(
                    payload
                    .hospitalization_number
                    .strip()
                ),

                patient_id=patient.id,

                service_id=service.id,

                admission_date=(
                    payload.admission_date
                ),

                discharge_date=(
                    payload.discharge_date
                ),
            )

            db.add(
                hospitalization
            )

            db.flush()

        # ====================================================
        # LINK DOCUMENT
        # ====================================================

        document.hospitalization_id = (
    hospitalization.id
)

        document.status = "ARCHIVED"

        document.archived_at = datetime.utcnow()
        

        create_audit_log(
    db,
    user=current_user,
    action="DOCUMENT_ARCHIVED",
    entity_type="DOCUMENT",
    entity_id=document.id,
    description=(
        f"L'archiviste '{current_user.username}' "
        f"a archivé le document "
        f"'{document.original_filename}'."
    ),
    details={
        "filename": document.original_filename,
        "hospitalization_number": (
            hospitalization.hospitalization_number
        ),
        "patient_id": str(patient.id),
        "hospitalization_id": (
            str(hospitalization.id)
        ),
        "service_id": str(service.id),
    },
)

        db.commit()

        return {

            "message":
                "Document archived successfully",

            "document_id":
                str(document.id),

            "patient_id":
                str(patient.id),

            "hospitalization_id":
                str(hospitalization.id),

            "service_id":
                str(service.id),

            "status":
                document.status,
        }

    except HTTPException:

        db.rollback()

        raise

    except Exception:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to archive document"
            ),
        )



# ============================================================
# ADMIN - UPDATE ARCHIVED DOCUMENT
# ============================================================

@router.patch(
    "/{document_id}/archive",
)
def update_archived_document(
    document_id: uuid.UUID,
    payload: DocumentVerificationRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(
        get_current_admin
    ),
):
    # Lock the document while the correction is being made.
    document = db.scalar(
        select(Document)
        .where(
            Document.id == document_id
        )
        .with_for_update()
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    if document.status != "ARCHIVED":
        raise HTTPException(
            status_code=400,
            detail=(
                "Only archived documents "
                "can be modified"
            ),
        )

    if document.hospitalization_id is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Archived document has no "
                "hospitalization"
            ),
        )

    if (
        payload.discharge_date
        and payload.discharge_date
        < payload.admission_date
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Discharge date cannot be "
                "before admission date"
            ),
        )

    try:
        # ====================================================
        # CURRENT DATA
        # ====================================================

        hospitalization = db.get(
            Hospitalization,
            document.hospitalization_id,
        )

        if hospitalization is None:
            raise HTTPException(
                status_code=404,
                detail="Hospitalization not found",
            )

        current_patient = db.get(
            Patient,
            hospitalization.patient_id,
        )

        if current_patient is None:
            raise HTTPException(
                status_code=404,
                detail="Patient not found",
            )

        # ====================================================
        # SERVICE
        # ====================================================

        try:
            service_id = uuid.UUID(
                payload.service_id
            )

        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid service ID",
            )

        service = db.get(
            Service,
            service_id,
        )

        if service is None:
            raise HTTPException(
                status_code=404,
                detail="Service not found",
            )

        # Note:
        # We intentionally allow an inactive service here.
        # This is historical archive correction, not creation
        # of a new hospitalization.

        # ====================================================
        # NORMALIZE INPUT
        # ====================================================

        cni = payload.cni.strip()

        first_name = (
            payload.first_name.strip()
        )

        last_name = (
            payload.last_name.strip()
        )

        hospitalization_number = (
            payload
            .hospitalization_number
            .strip()
        )

        if not cni:
            raise HTTPException(
                status_code=400,
                detail="CNI cannot be empty",
            )

        if not first_name:
            raise HTTPException(
                status_code=400,
                detail="First name cannot be empty",
            )

        if not last_name:
            raise HTTPException(
                status_code=400,
                detail="Last name cannot be empty",
            )

        if not hospitalization_number:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Hospitalization number "
                    "cannot be empty"
                ),
            )

        # ====================================================
        # SAVE BEFORE VALUES FOR AUDIT
        # ====================================================

        old_values = {
            "cni": current_patient.cni,
            "first_name": (
                current_patient.first_name
            ),
            "last_name": (
                current_patient.last_name
            ),
            "hospitalization_number": (
                hospitalization
                .hospitalization_number
            ),
            "service_id": str(
                hospitalization.service_id
            ),
            "admission_date": (
                hospitalization
                .admission_date
                .isoformat()
            ),
            "discharge_date": (
                hospitalization
                .discharge_date
                .isoformat()
                if hospitalization.discharge_date
                else None
            ),
        }

        # ====================================================
        # HOSPITALIZATION NUMBER CONFLICT
        # ====================================================

        conflicting_hospitalization = (
            db.scalar(
                select(Hospitalization)
                .where(
                    Hospitalization
                    .hospitalization_number
                    == hospitalization_number,
                    Hospitalization.id
                    != hospitalization.id,
                )
            )
        )

        if conflicting_hospitalization:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Hospitalization number "
                    "already belongs to another "
                    "hospitalization"
                ),
            )

        # ====================================================
        # PATIENT
        # ====================================================
        #
        # Patient records may be shared by several
        # hospitalizations.
        #
        # Therefore:
        #
        # 1. If the requested CNI already belongs to another
        #    patient, link the hospitalization to that patient
        #    only if the names also match.
        #
        # 2. If changing the identity of a patient who has
        #    several hospitalizations, create a new patient
        #    instead of modifying all historical records.
        #
        # 3. Otherwise update the current patient directly.
        # ====================================================

        patient_with_cni = db.scalar(
            select(Patient).where(
                Patient.cni == cni
            )
        )

        patient: Patient

        if (
            patient_with_cni is not None
            and
            patient_with_cni.id
            != current_patient.id
        ):
            names_match = (
                patient_with_cni
                .first_name
                .strip()
                .lower()
                == first_name.lower()
                and
                patient_with_cni
                .last_name
                .strip()
                .lower()
                == last_name.lower()
            )

            if not names_match:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "The requested CNI "
                        "already belongs to another "
                        "patient with different names"
                    ),
                )

            # Relink only this hospitalization.
            patient = patient_with_cni

            hospitalization.patient_id = (
                patient.id
            )

        else:
            identity_changed = (
                current_patient.cni != cni
                or
                current_patient
                .first_name
                .strip()
                .lower()
                != first_name.lower()
                or
                current_patient
                .last_name
                .strip()
                .lower()
                != last_name.lower()
            )

            hospitalization_count = (
                db.scalar(
                    select(
                        func.count(
                            Hospitalization.id
                        )
                    )
                    .where(
                        Hospitalization
                        .patient_id
                        == current_patient.id
                    )
                )
                or 0
            )

            if (
                identity_changed
                and hospitalization_count > 1
            ):
                # Do not modify patient data used by
                # other hospitalizations.

                patient = Patient(
                    cni=cni,
                    first_name=first_name,
                    last_name=last_name,
                )

                db.add(patient)

                db.flush()

                hospitalization.patient_id = (
                    patient.id
                )

            else:
                patient = current_patient

                patient.cni = cni

                patient.first_name = (
                    first_name
                )

                patient.last_name = (
                    last_name
                )

        # ====================================================
        # UPDATE HOSPITALIZATION
        # ====================================================

        hospitalization.hospitalization_number = (
            hospitalization_number
        )

        hospitalization.service_id = (
            service.id
        )

        hospitalization.admission_date = (
            payload.admission_date
        )

        hospitalization.discharge_date = (
            payload.discharge_date
        )

        # ====================================================
        # IMPORTANT
        # ====================================================
        #
        # Do NOT modify:
        #
        # document.archived_at
        # DocumentAIResult
        # DocumentExtraction
        #
        # archived_at = original archival timestamp.
        # AI/OCR = original machine extraction history.
        #
        # The verified Patient/Hospitalization values are the
        # corrected archive data.
        # ====================================================

        new_values = {
            "cni": patient.cni,
            "first_name": (
                patient.first_name
            ),
            "last_name": (
                patient.last_name
            ),
            "hospitalization_number": (
                hospitalization
                .hospitalization_number
            ),
            "service_id": str(
                hospitalization.service_id
            ),
            "admission_date": (
                hospitalization
                .admission_date
                .isoformat()
            ),
            "discharge_date": (
                hospitalization
                .discharge_date
                .isoformat()
                if hospitalization.discharge_date
                else None
            ),
        }

        # ====================================================
        # AUDIT
        # ====================================================

        create_audit_log(
            db,
            user=current_admin,
            action="DOCUMENT_ARCHIVE_UPDATED",
            entity_type="DOCUMENT",
            entity_id=document.id,
            description=(
                f"L'administrateur "
                f"'{current_admin.username}' "
                f"a modifié le document archivé "
                f"'{document.original_filename}'."
            ),
            details={
                "filename": (
                    document.original_filename
                ),
                "old_values": old_values,
                "new_values": new_values,
            },
        )

        db.commit()

        return {
            "message": (
                "Archived document updated "
                "successfully"
            ),
            "document_id": str(
                document.id
            ),
            "patient_id": str(
                patient.id
            ),
            "hospitalization_id": str(
                hospitalization.id
            ),
            "service_id": str(
                service.id
            ),
            "status": document.status,
            "data": new_values,
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to update archived "
                "document"
            ),
        )


# ============================================================
# ADMIN - RESUME DOCUMENT PROCESSING
# ============================================================

@router.post(
    "/{document_id}/resume",
)
def resume_document_processing(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_admin: User = Depends(
        get_current_admin
    ),
):
    document = db.scalar(
        select(Document)
        .where(
            Document.id == document_id
        )
        .with_for_update()
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    current_status = (
        document.status
        .strip()
        .upper()
    )

    # Already finished.
    if current_status == "ARCHIVED":
        raise HTTPException(
            status_code=400,
            detail=(
                "Document is already archived"
            ),
        )

    # This is not an error.
    # Automatic processing has finished and
    # human verification is required.
    if current_status == "READY_FOR_REVIEW":
        raise HTTPException(
            status_code=400,
            detail=(
                "Document processing is already "
                "complete and is waiting for review"
            ),
        )

    # Avoid starting a second Celery job while another
    # worker may currently be processing the document.
    if current_status in {
        "OCR_PROCESSING",
        "AI_PROCESSING",
    }:
        raise HTTPException(
            status_code=409,
            detail=(
                "Document is currently being "
                "processed"
            ),
        )

    resumable_statuses = {
        "IMPORTED",
        "OCR_ERROR",
        "AI_ERROR",
        "PROCESSING_ERROR",
        "ARCHIVE_ERROR",
    }

    if current_status not in resumable_statuses:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Document cannot be resumed "
                f"from status {current_status}"
            ),
        )

    file_path = Path(
        document.storage_path
    )

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Document file not found",
        )

    try:
        # Keep the current status until the worker
        # actually starts processing.
        #
        # This avoids showing OCR_PROCESSING while
        # the task is still waiting inside Redis.

        task = process_document.delay(
            str(document.id)
        )

        create_audit_log(
            db,
            user=current_admin,
            action="DOCUMENT_PROCESSING_RESUMED",
            entity_type="DOCUMENT",
            entity_id=document.id,
            description=(
                f"L'administrateur "
                f"'{current_admin.username}' "
                f"a repris le traitement du document "
                f"'{document.original_filename}' "
                f"depuis le statut '{current_status}'."
            ),
            details={
                "filename": (
                    document.original_filename
                ),
                "previous_status": (
                    current_status
                ),
                "celery_task_id": (
                    task.id
                ),
            },
        )

        db.commit()

        return {
            "message": (
                "Document processing has been "
                "queued for resumption"
            ),
            "document_id": str(
                document.id
            ),
            "previous_status": (
                current_status
            ),
            "task_id": task.id,
        }

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=503,
            detail=(
                "Document exists but processing "
                "could not be queued"
            ),
        )
