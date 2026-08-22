from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.service import Service
from app.models.user import User
from app.schemas.service import (
    ServiceCreate,
    ServiceResponse,
)

from app.api.dependencies import (
    get_current_admin,
    get_current_user,
)

import uuid

from app.services.audit_service import create_audit_log


router = APIRouter(
    prefix="/services",
    tags=["Services"],
)


@router.post(
    "",
    response_model=ServiceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_service(
    data: ServiceCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    name = data.name.strip()

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Service name cannot be empty",
        )

    existing = db.scalar(
        select(Service).where(
            Service.name.ilike(name)
        )
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Service already exists",
        )

    service = Service(
        name=name,
        is_active=True,
    )

    db.add(service)

    db.flush()

    create_audit_log(
    db,
    user=current_admin,
    action="SERVICE_CREATED",
    entity_type="SERVICE",
    entity_id=service.id,
    description=(
        f"L'administrateur '{current_admin.username}' "
        f"a créé le service '{service.name}'."
    ),
    details={
        "service_name": service.name,
    },
)

    db.commit()
    db.refresh(service)

    return service


@router.get(
    "",
    response_model=list[ServiceResponse],
)
def get_services(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.scalars(
        select(Service)
        .order_by(Service.name)
    ).all()




@router.patch(
    "/{service_id}/status",
    response_model=ServiceResponse,
)
def update_service_status(
    service_id: uuid.UUID,
    is_active: bool,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
):
    service = db.get(
        Service,
        service_id,
    )

    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found",
        )

    old_status = service.is_active

    service.is_active = is_active

    create_audit_log(
    db,
    user=current_admin,
    action="SERVICE_STATUS_CHANGED",
    entity_type="SERVICE",
    entity_id=service.id,
    description=(
        f"L'administrateur '{current_admin.username}' "
        f"a modifié le statut du service '{service.name}' "
        f"de {'actif' if old_status else 'inactif'} "
        f"à {'actif' if is_active else 'inactif'}."
    ),
    details={
        "service_name": service.name,
        "old_status": old_status,
        "new_status": is_active,
    },
)

    db.commit()
    db.refresh(service)

    return service
