import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.hospitalization import Hospitalization
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User
from app.schemas.hospitalization import (
    HospitalizationCreate,
    HospitalizationResponse,
)

router = APIRouter(
    prefix="/hospitalizations",
    tags=["Hospitalizations"],
)

@router.post(
    "",
    response_model=HospitalizationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_hospitalization(
    data: HospitalizationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    patient = db.get(
        Patient,
        uuid.UUID(data.patient_id),
    )

    if not patient:
        raise HTTPException(
            status_code=404,
            detail="Patient not found",
        )

    service = db.get(
        Service,
        uuid.UUID(data.service_id),
    )

    if not service:
        raise HTTPException(
            status_code=404,
            detail="Service not found",
        )

    existing = db.scalar(
        select(Hospitalization).where(
            Hospitalization.hospitalization_number
            == data.hospitalization_number
        )
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Hospitalization number already exists",
        )

    hospitalization = Hospitalization(
        hospitalization_number=data.hospitalization_number,
        patient_id=uuid.UUID(data.patient_id),
        service_id=uuid.UUID(data.service_id),
        admission_date=data.admission_date,
        discharge_date=data.discharge_date,
    )

    db.add(hospitalization)
    db.commit()
    db.refresh(hospitalization)

    return hospitalization


