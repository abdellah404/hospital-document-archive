from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: UUID
    hospitalization_id: UUID
    original_filename: str
    status: str
    created_at: datetime