from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.patient import Patient


def identify_patient(
    db: Session,
    cni: str | None,
    first_name: str | None,
    last_name: str | None,
):
    if not cni:
        return {
            "status": "IDENTIFICATION_REQUIRED",
            "patient": None,
        }

    patient = db.scalar(
        select(Patient).where(
            Patient.cni == cni
        )
    )

    if patient is None:
        return {
            "status": "NEW_PATIENT",
            "patient": None,
        }

    # Patient exists.
    # Now compare the extracted names with DB values.
    first_name_matches = (
        not first_name
        or patient.first_name.lower() == first_name.lower()
    )

    last_name_matches = (
        not last_name
        or patient.last_name.lower() == last_name.lower()
    )

    if first_name_matches and last_name_matches:
        return {
            "status": "PATIENT_MATCHED",
            "patient": patient,
        }

    return {
        "status": "PATIENT_CONFLICT",
        "patient": patient,
    }