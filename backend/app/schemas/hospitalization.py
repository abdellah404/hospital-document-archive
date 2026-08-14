from datetime import date
from uuid import UUID

from pydantic import BaseModel


class HospitalizationCreate(BaseModel):
    hospitalization_number: str
    patient_id: str
    service_id: str
    admission_date: date
    discharge_date: date | None = None


class HospitalizationResponse(BaseModel):
    id: UUID
    hospitalization_number: str
    patient_id: UUID
    service_id: UUID
    admission_date: date
    discharge_date: date | None