from datetime import date

from pydantic import BaseModel


class DocumentAIResultResponse(BaseModel):

    cni: str | None = None

    first_name: str | None = None

    last_name: str | None = None

    hospitalization_number: str | None = None

    service_name: str | None = None

    admission_date: date | None = None

    discharge_date: date | None = None


class DocumentReviewResponse(BaseModel):

    document_id: str

    original_filename: str

    status: str

    ai_result: DocumentAIResultResponse

    matched_patient_id: str | None = None

    matched_hospitalization_id: str | None = None

    matched_service_id: str | None = None