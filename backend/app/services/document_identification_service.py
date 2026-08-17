from sqlalchemy.orm import Session

from app.services.hospitalization_matching_service import (
    identify_hospitalization,
)

from app.services.patient_matching_service import (
    identify_patient,
)

from app.services.service_matching_service import (
    identify_service,
)


def identify_document(
    db: Session,
    *,
    cni: str | None,
    first_name: str | None,
    last_name: str | None,
    hospitalization_number: str | None,
    service_name: str | None,
):

    patient_result = identify_patient(
        db=db,
        cni=cni,
        first_name=first_name,
        last_name=last_name,
    )

    hospitalization_result = (
        identify_hospitalization(
            db=db,
            hospitalization_number=(
                hospitalization_number
            ),
        )
    )

    service_result = identify_service(
        db=db,
        service_name=service_name,
    )

    return {
        "patient": patient_result,
        "hospitalization": hospitalization_result,
        "service": service_result,
    }