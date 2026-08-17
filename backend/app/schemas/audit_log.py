from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: UUID

    user_id: UUID | None

    username: str | None

    action: str

    entity_type: str

    entity_id: UUID | None

    description: str

    details: dict | None

    created_at: datetime