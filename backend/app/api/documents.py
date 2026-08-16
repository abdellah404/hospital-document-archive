import uuid
from pathlib import Path
from fastapi.responses import FileResponse
from sqlalchemy import select

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.document import Document
from app.models.hospitalization import Hospitalization
from app.models.user import User
from app.schemas.document import DocumentResponse
from app.schemas import document
from app.models.document_ai_result import DocumentAIResult
from app.models.service import Service


from app.models.document_extraction import (
    DocumentExtraction,
)

from app.services.ocr_service import (
    extract_text_from_pdf,
)


from app.services.ai_service import (
    extract_patient_information,
)

#import identify_document

from app.services.document_identification_service import (
    identify_document,
)
from app.models.patient import Patient
from app.schemas.document_verification import DocumentVerificationRequest


router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)


STORAGE_DIR = Path("storage/documents")
STORAGE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    hospitalization_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    #current_user: User = Depends(get_current_user),
):

    hospitalization = db.get(
        Hospitalization,
        hospitalization_id,
    )

    if not hospitalization:
        raise HTTPException(
            status_code=404,
            detail="Hospitalization not found",
        )
    
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed",
        )


    document_id = uuid.uuid4()

    stored_filename = f"{document_id}.pdf"

    file_path = STORAGE_DIR / stored_filename

    try:
        with file_path.open("wb") as buffer:
            while chunk := await file.read(1024 * 1024):
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
        hospitalization_id=hospitalization_id,
        original_filename=file.filename or "document.pdf",
        stored_filename=stored_filename,
        storage_path=str(file_path),
        status="IMPORTED",
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return document



@router.get(
    "",
    response_model=list[DocumentResponse],
)
def get_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.scalars(
        select(Document)
        .order_by(Document.created_at.desc())
    ).all()

@router.get(
    "/{document_id}/file",
)
def get_document_file(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = db.get(Document, document_id)

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    file_path = Path(document.storage_path)

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




@router.post(
    "/{document_id}/ocr",
)
def process_document_ocr(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    #current_user: User = Depends(get_current_user),
):
    document = db.get(
        Document,
        document_id,
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    file_path = Path(document.storage_path)

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Document file not found",
        )

    document.status = "OCR_PROCESSING"

    db.commit()

    try:
        text = extract_text_from_pdf(
            str(file_path)
        )

        extraction = db.scalar(
            select(DocumentExtraction).where(
                DocumentExtraction.document_id
                == document.id
            )
        )

        if extraction:
            extraction.ocr_text = text
        else:
            extraction = DocumentExtraction(
                document_id=document.id,
                ocr_text=text,
            )

            db.add(extraction)

        document.status = "AI_PROCESSING"

        db.commit()

        return {
            "document_id": str(document.id),
            "status": document.status,
            "message": "OCR completed successfully",
        }

    except Exception:
        document.status = "OCR_ERROR"

        db.commit()

        raise HTTPException(
            status_code=500,
            detail="OCR processing failed",
        )



@router.post("/{document_id}/analyze")
def analyze_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    #current_user: User = Depends(get_current_user),
):
    document = db.get(
        Document,
        document_id,
    )

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    extraction = db.scalar(
        select(DocumentExtraction).where(
            DocumentExtraction.document_id == document.id
        )
    )

    if not extraction:
        raise HTTPException(
            status_code=400,
            detail="OCR has not been completed",
        )

    services = db.scalars(
        select(Service)
        .where(Service.is_active == True)
    ).all()

    service_names = [
        service.name
        for service in services
    ]

    document.status = "AI_PROCESSING"
    db.commit()

    try:
        result = extract_patient_information(
            extraction.ocr_text,
            service_names,
        )

        ai_result = db.scalar(
            select(DocumentAIResult).where(
                DocumentAIResult.document_id
                == document.id
            )
        )

        if not ai_result:
            ai_result = DocumentAIResult(
                document_id=document.id,
            )
            db.add(ai_result)

        ai_result.cni = result.get("cni")
        ai_result.first_name = result.get("first_name")
        ai_result.last_name = result.get("last_name")
        ai_result.hospitalization_number = result.get(
            "hospitalization_number"
        )
        ai_result.service_name = result.get(
            "service"
        )

        document.status = "READY_FOR_REVIEW"

        db.commit()
        db.refresh(ai_result)

        return {
            "document_id": str(document.id),
            "status": document.status,
            "ai_result": {
                "cni": ai_result.cni,
                "first_name": ai_result.first_name,
                "last_name": ai_result.last_name,
                "hospitalization_number":
                    ai_result.hospitalization_number,
                "service_name":
                    ai_result.service_name,
            },
        }

    except Exception:
        document.status = "AI_ERROR"
        db.commit()

        raise HTTPException(
            status_code=500,
            detail="AI analysis failed",
        )




@router.get("/{document_id}/review")
def review_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    #current_user: User = Depends(get_current_user),
):
    document = db.get(Document, document_id)

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    ai_result = db.scalar(
        select(DocumentAIResult).where(
            DocumentAIResult.document_id == document.id
        )
    )

    if not ai_result:
        raise HTTPException(
            status_code=400,
            detail="AI analysis has not been completed",
        )

    identification = identify_document(
        db=db,
        cni=ai_result.cni,
        first_name=ai_result.first_name,
        last_name=ai_result.last_name,
        hospitalization_number=(
            ai_result.hospitalization_number
        ),
        service_name=ai_result.service_name,
    )

    return {
        "document": {
            "id": str(document.id),
            "filename": document.original_filename,
            "status": document.status,
        },

        "ai": {
            "cni": ai_result.cni,
            "first_name": ai_result.first_name,
            "last_name": ai_result.last_name,
            "hospitalization_number": (
                ai_result.hospitalization_number
            ),
            "service_name": ai_result.service_name,
        },

        "identification": {
            "patient": {
                "status": identification["patient"]["status"],
                "id": (
                    str(
                        identification["patient"]["patient"].id
                    )
                    if identification["patient"]["patient"]
                    else None
                ),
            },

            "hospitalization": {
                "status": (
                    identification["hospitalization"]["status"]
                ),
                "id": (
                    str(
                        identification["hospitalization"]
                        ["hospitalization"].id
                    )
                    if identification["hospitalization"]
                    ["hospitalization"]
                    else None
                ),
            },

            "service": {
                "status": identification["service"]["status"],
                "id": (
                    str(
                        identification["service"]["service"].id
                    )
                    if identification["service"]["service"]
                    else None
                ),
            },
        },
    }




@router.post("/{document_id}/verify")
def verify_document(
    document_id: uuid.UUID,
    payload: DocumentVerificationRequest,
    db: Session = Depends(get_db),
    #current_user: User = Depends(get_current_user),
):
    document = db.get(Document, document_id)

    if not document:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    if document.status != "READY_FOR_REVIEW":
        raise HTTPException(
            status_code=400,
            detail="Document is not ready for verification",
        )

    service = db.get(Service, payload.service_id)

    if not service:
        raise HTTPException(
            status_code=400,
            detail="Service not found",
        )

    if not service.is_active:
        raise HTTPException(
            status_code=400,
            detail="Service is inactive",
        )

    # -------------------------
    # Patient
    # -------------------------

    patient = db.scalar(
        select(Patient).where(
            Patient.cni == payload.cni
        )
    )

    if patient:
        if (
            patient.first_name.lower()
            != payload.first_name.lower()
            or
            patient.last_name.lower()
            != payload.last_name.lower()
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Patient information conflicts "
                    "with existing patient"
                ),
            )

    else:
        patient = Patient(
            cni=payload.cni,
            first_name=payload.first_name,
            last_name=payload.last_name,
        )

        db.add(patient)
        db.flush()

    # -------------------------
    # Hospitalization
    # -------------------------

    hospitalization = db.scalar(
        select(Hospitalization).where(
            Hospitalization.hospitalization_number
            == payload.hospitalization_number
        )
    )

    if hospitalization:

        if hospitalization.patient_id != patient.id:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Hospitalization belongs "
                    "to another patient"
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
                    "Hospitalization already has "
                    "an archived document"
                ),
            )

    else:
        hospitalization = Hospitalization(
            hospitalization_number=(
                payload.hospitalization_number
            ),
            patient_id=patient.id,
            service_id=service.id,
        )

        db.add(hospitalization)
        db.flush()

    # -------------------------
    # Document
    # -------------------------

    document.hospitalization_id = (
        hospitalization.id
    )

    document.status = "VERIFIED"

    db.commit()

    return {
        "message": "Document verified successfully",
        "document_id": str(document.id),
        "patient_id": str(patient.id),
        "hospitalization_id": str(
            hospitalization.id
        ),
        "service_id": str(service.id),
        "status": document.status,
    }

    