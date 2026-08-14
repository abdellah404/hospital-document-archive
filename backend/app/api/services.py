from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.service import Service
from app.models.user import User
from app.schemas.service import (
    ServiceCreate,
    ServiceResponse,
)

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
    current_user: User = Depends(get_current_user),
):
    existing = db.scalar(
        select(Service).where(Service.name == data.name)
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Service already exists",
        )

    service = Service(
        name=data.name,
    )

    db.add(service)
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
        .where(Service.is_active == True)
    ).all()