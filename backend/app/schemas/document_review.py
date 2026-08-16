from pydantic import BaseModel


class DocumentAIResultResponse(BaseModel):
    cni: str | None
    first_name: str | None
    last_name: str | None
    hospitalization_number: str | None
    service_name: str | None


class DocumentReviewResponse(BaseModel):
    document_id: str
    original_filename: str
    status: str

    ai_result: DocumentAIResultResponse

    matched_patient_id: str | None
    matched_hospitalization_id: str | None
    matched_service_id: str | None