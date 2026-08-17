import uuid

from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)

from fastapi.responses import (
    FileResponse,
)

from sqlalchemy import select

from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_user,
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