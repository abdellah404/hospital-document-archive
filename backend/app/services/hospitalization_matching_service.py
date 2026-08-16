from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.hospitalization import Hospitalization


def identify_hospitalization(
    db: Session,
    hospitalization_number: str | None,
):
    if not hospitalization_number:
        return {
            "status": "IDENTIFICATION_REQUIRED",
            "hospitalization": None,
        }

    hospitalization = db.scalar(
        select(Hospitalization).where(
            Hospitalization.hospitalization_number
            == hospitalization_number
        )
    )

    if hospitalization is None:
        return {
            "status": "NEW_HOSPITALIZATION",
            "hospitalization": None,
        }

    return {
        "status": "HOSPITALIZATION_FOUND",
        "hospitalization": hospitalization,
    }