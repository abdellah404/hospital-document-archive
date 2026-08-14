from datetime import datetime

from pydantic import BaseModel, ConfigDict
from uuid import UUID


class PatientCreate(BaseModel):
    cni: str
    first_name: str
    last_name: str


class PatientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    cni: str
    first_name: str
    last_name: str
    created_at: datetime