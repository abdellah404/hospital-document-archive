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

    autoretry_for = (
        Exception,
    )

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
        # DOCUMENT
        # =====================================================

        document = db.get(
            Document,
            document_id,
        )

        if document is None:
            return {
                "status": (
                    "DOCUMENT_NOT_FOUND"
                ),
                "document_id": (
                    document_id
                ),
            }

        current_status = (
            document.status
            .strip()
            .upper()
        )

        # =====================================================
        # ALREADY FINISHED
        # =====================================================

        if current_status == "ARCHIVED":
            return {
                "status": "ARCHIVED",
                "document_id": (
                    document_id
                ),
            }

        if (
            current_status
            == "READY_FOR_REVIEW"
        ):
            return {
                "status": (
                    "READY_FOR_REVIEW"
                ),
                "document_id": (
                    document_id
                ),
            }

        # =====================================================
        # FILE
        # =====================================================

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
        # CHECK OCR CHECKPOINT
        # =====================================================

        extraction = db.scalar(
            select(
                DocumentExtraction
            ).where(
                DocumentExtraction
                .document_id
                == document.id
            )
        )

        # =====================================================
        # OCR
        # =====================================================
        #
        # Only execute OCR when no successful OCR
        # extraction already exists.
        # =====================================================

        if extraction is None:

            document.status = (
                "OCR_PROCESSING"
            )

            db.commit()

            try:
                text = (
                    extract_text_from_pdf(
                        str(file_path)
                    )
                )

            except Exception:

                document.status = (
                    "OCR_ERROR"
                )

                db.commit()

                raise

            extraction = (
                DocumentExtraction(
                    document_id=(
                        document.id
                    ),
                    ocr_text=text,
                )
            )

            db.add(
                extraction
            )

            # This commit is an important checkpoint.
            #
            # If AI fails later, OCR remains safely stored.
            db.commit()

        else:
            text = (
                extraction.ocr_text
            )

        # =====================================================
        # CHECK AI CHECKPOINT
        # =====================================================

        ai_result = db.scalar(
            select(
                DocumentAIResult
            ).where(
                DocumentAIResult
                .document_id
                == document.id
            )
        )

        # =====================================================
        # AI
        # =====================================================
        #
        # Only execute Gemini when no successfully persisted
        # AI result exists.
        # =====================================================

        if ai_result is None:

            document.status = (
                "AI_PROCESSING"
            )

            db.commit()

            services = db.scalars(
                select(Service).where(
                    Service
                    .is_active
                    .is_(True)
                )
            ).all()

            service_names = [
                service.name
                for service
                in services
            ]

            if not service_names:

                document.status = (
                    "AI_ERROR"
                )

                db.commit()

                raise ValueError(
                    "No active hospital "
                    "services exist"
                )

            try:
                result = (
                    extract_patient_information(
                        text,
                        service_names,
                    )
                )

            except Exception:

                document.status = (
                    "AI_ERROR"
                )

                db.commit()

                raise

            # =================================================
            # BUILD AI RESULT
            # =================================================

            ai_result = (
                DocumentAIResult(
                    document_id=(
                        document.id
                    ),
                )
            )

            ai_result.cni = (
                result.get(
                    "cni"
                )
            )

            ai_result.first_name = (
                result.get(
                    "first_name"
                )
            )

            ai_result.last_name = (
                result.get(
                    "last_name"
                )
            )

            ai_result.hospitalization_number = (
                result.get(
                    "hospitalization_number"
                )
            )

            ai_result.service_name = (
                result.get(
                    "service"
                )
            )

            admission_date = (
                result.get(
                    "admission_date"
                )
            )

            discharge_date = (
                result.get(
                    "discharge_date"
                )
            )

            try:
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

            except ValueError:

                document.status = (
                    "AI_ERROR"
                )

                db.commit()

                raise ValueError(
                    "AI returned an invalid "
                    "date format"
                )

            db.add(
                ai_result
            )

            # =================================================
            # AI CHECKPOINT
            # =================================================
            #
            # Commit the AI result separately.
            #
            # This means a later crash does not force
            # Gemini to run again.
            # =================================================

            db.commit()

        # =====================================================
        # READY FOR HUMAN REVIEW
        # =====================================================

        document.status = (
            "READY_FOR_REVIEW"
        )

        db.commit()

        return {
            "status": (
                "READY_FOR_REVIEW"
            ),
            "document_id": (
                document_id
            ),
        }

    except Exception:

        db.rollback()

        document = db.get(
            Document,
            document_id,
        )

        if document is not None:

            # Keep precise errors.
            #
            # Do not replace OCR_ERROR or AI_ERROR
            # with a generic error.

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