from pydantic import BaseModel, ConfigDict
from uuid import UUID


class ServiceCreate(BaseModel):
    name: str


class ServiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    is_active: bool

    
    