from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    hospitalization_id: UUID | None
    original_filename: str
    status: str
    created_at: datetime


class ArchivedPatientResponse(BaseModel):
    id: UUID
    cni: str
    first_name: str
    last_name: str


class ArchivedHospitalizationResponse(BaseModel):
    id: UUID
    number: str
    admission_date: date | None
    discharge_date: date | None


class ArchivedServiceResponse(BaseModel):
    id: UUID
    name: str
    is_active: bool


class ArchivedDocumentResponse(BaseModel):
    id: UUID
    original_filename: str
    status: str
    created_at: datetime
    archived_at: datetime | None
    patient: ArchivedPatientResponse
    hospitalization: ArchivedHospitalizationResponse
    service: ArchivedServiceResponse
