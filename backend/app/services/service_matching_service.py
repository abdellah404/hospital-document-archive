from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.service import Service


def identify_service(
    db: Session,
    service_name: str | None,
):
    if not service_name:
        return {
            "status": "IDENTIFICATION_REQUIRED",
            "service": None,
        }

    service = db.scalar(
        select(Service).where(
            Service.name.ilike(service_name)
        )
    )

    if service is None:
        return {
            "status": "SERVICE_NOT_FOUND",
            "service": None,
        }

    return {
        "status": "SERVICE_FOUND",
        "service": service,
    }