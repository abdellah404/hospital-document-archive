import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.patient import Patient
from app.models.user import User
from app.schemas.patient import (
    PatientCreate,
    PatientResponse,
)

router = APIRouter(
    prefix="/patients",
    tags=["Patients"],
)

@router.post(
    "",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_patient(
    data: PatientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = db.scalar(
        select(Patient).where(Patient.cni == data.cni)
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Patient with this CNI already exists",
        )

    patient = Patient(
        cni=data.cni,
        first_name=data.first_name,
        last_name=data.last_name,
    )

    db.add(patient)
    db.commit()
    db.refresh(patient)

    return patient

@router.get(
    "",
    response_model=list[PatientResponse],
)
def get_patients(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.scalars(
        select(Patient)
    ).all()

@router.get(
    "/{patient_id}",
    response_model=PatientResponse,
)
def get_patient(
    patient_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    patient = db.get(Patient, patient_id)

    if not patient:
        raise HTTPException(
            status_code=404,
            detail="Patient not found",
        )

    return patient