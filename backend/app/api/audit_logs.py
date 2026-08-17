from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_admin
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit_log import AuditLogResponse


router = APIRouter(
    prefix="/audit-logs",
    tags=["Audit Logs"],
)


@router.get(
    "",
    response_model=list[AuditLogResponse],
)
def get_audit_logs(
    user_id: UUID | None = Query(
        default=None,
    ),
    action: str | None = Query(
        default=None,
    ),
    entity_type: str | None = Query(
        default=None,
    ),
    from_date: datetime | None = Query(
        default=None,
    ),
    to_date: datetime | None = Query(
        default=None,
    ),
    page: int = Query(
        default=1,
        ge=1,
    ),
    page_size: int = Query(
        default=50,
        ge=1,
        le=100,
    ),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    query = (
        select(
            AuditLog,
            User.username,
        )
        .outerjoin(
            User,
            AuditLog.user_id == User.id,
        )
    )

    if user_id is not None:
        query = query.where(
            AuditLog.user_id == user_id
        )

    if action is not None:
        query = query.where(
            AuditLog.action == action
        )

    if entity_type is not None:
        query = query.where(
            AuditLog.entity_type == entity_type
        )

    if from_date is not None:
        query = query.where(
            AuditLog.created_at >= from_date
        )

    if to_date is not None:
        query = query.where(
            AuditLog.created_at <= to_date
        )

    offset = (
        page - 1
    ) * page_size

    rows = db.execute(
        query
        .order_by(
            AuditLog.created_at.desc()
        )
        .offset(offset)
        .limit(page_size)
    ).all()

    return [
        {
            "id": audit_log.id,
            "user_id": audit_log.user_id,
            "username": username,
            "action": audit_log.action,
            "entity_type": audit_log.entity_type,
            "entity_id": audit_log.entity_id,
            "description": audit_log.description,
            "details": audit_log.details,
            "created_at": audit_log.created_at,
        }
        for audit_log, username in rows
    ]