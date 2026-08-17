from datetime import date
from pathlib import Path

from celery import Task
from sqlalchemy import select

from app.db.session import SessionLocal

from app.models.document import Document
from app.models.document_ai_result import (
    DocumentAIResult,
)
from app.models.document_extraction import (
    DocumentExtraction,
)

from app.models.service import Service

from app.services.ai_service import (
    extract_patient_information,
)

from app.services.ocr_service import (
    extract_text_from_pdf,
)

from app.tasks.celery_app import (
    celery_app,
)


class DatabaseTask(Task):

    autoretry_for = (Exception,)

    retry_backoff = True

    retry_jitter = True

    retry_kwargs = {
        "max_retries": 3,
    }

@celery_app.task(
    bind=True,
    base=DatabaseTask,
)
def process_document(
    self,
    document_id: str,
):

    db = SessionLocal()

    try:

        # =====================================================
        # FIND DOCUMENT
        # =====================================================

        document = db.get(
            Document,
            document_id,
        )

        if document is None:
            return {
                "status": "DOCUMENT_NOT_FOUND",
                "document_id": document_id,
            }

        file_path = Path(
            document.storage_path
        )

        if not file_path.exists():

            document.status = (
                "PROCESSING_ERROR"
            )

            db.commit()

            raise FileNotFoundError(
                f"Document file not found: "
                f"{file_path}"
            )

        # =====================================================
        # OCR
        # =====================================================

        document.status = "OCR_PROCESSING"

        db.commit()

        try:

            text = extract_text_from_pdf(
                str(file_path)
            )

        except Exception:

            document.status = "OCR_ERROR"

            db.commit()

            raise

        extraction = db.scalar(
            select(DocumentExtraction).where(
                DocumentExtraction.document_id
                == document.id
            )
        )

        if extraction is None:

            extraction = DocumentExtraction(
                document_id=document.id,
                ocr_text=text,
            )

            db.add(extraction)

        else:

            extraction.ocr_text = text

        db.commit()

        # =====================================================
        # AI
        # =====================================================

        document.status = "AI_PROCESSING"

        db.commit()

        services = db.scalars(
            select(Service).where(
                Service.is_active.is_(True)
            )
        ).all()

        service_names = [
            service.name
            for service in services
        ]

        if not service_names:
            raise ValueError(
                "No active hospital services exist"
            )

        try:

            result = (
                extract_patient_information(
                    text,
                    service_names,
                )
            )

        except Exception:

            document.status = "AI_ERROR"

            db.commit()

            raise

        # =====================================================
        # SAVE AI RESULT
        # =====================================================

        ai_result = db.scalar(
            select(DocumentAIResult).where(
                DocumentAIResult.document_id
                == document.id
            )
        )

        if ai_result is None:

            ai_result = DocumentAIResult(
                document_id=document.id,
            )

            db.add(ai_result)

        ai_result.cni = result.get(
            "cni"
        )

        ai_result.first_name = result.get(
            "first_name"
        )

        ai_result.last_name = result.get(
            "last_name"
        )

        ai_result.hospitalization_number = (
            result.get(
                "hospitalization_number"
            )
        )

        ai_result.service_name = (
            result.get("service")
        )

        admission_date = result.get(
            "admission_date"
        )

        discharge_date = result.get(
            "discharge_date"
        )

        ai_result.admission_date = (
            date.fromisoformat(
                admission_date
            )
            if admission_date
            else None
        )

        ai_result.discharge_date = (
            date.fromisoformat(
                discharge_date
            )
            if discharge_date
            else None
        )

        # =====================================================
        # READY FOR MANUAL ARCHIVIST REVIEW
        # =====================================================

        document.status = (
            "READY_FOR_REVIEW"
        )

        db.commit()

        return {
            "status": "READY_FOR_REVIEW",
            "document_id": document_id,
        }

    except Exception:

        db.rollback()

        # Do not overwrite specific OCR/AI
        # errors with generic PROCESSING_ERROR.

        document = db.get(
            Document,
            document_id,
        )

        if document is not None:

            if document.status not in {
                "OCR_ERROR",
                "AI_ERROR",
            }:

                document.status = (
                    "PROCESSING_ERROR"
                )

                db.commit()

        raise

    finally:

        db.close()
