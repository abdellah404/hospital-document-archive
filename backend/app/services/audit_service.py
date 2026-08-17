import uuid

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User


def create_audit_log(
    db: Session,
    *,
    user: User,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    description: str,
    details: dict | None = None,
) -> AuditLog:

    audit_log = AuditLog(
        user_id=user.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        description=description,
        details=details,
    )

    db.add(audit_log)

    return audit_log