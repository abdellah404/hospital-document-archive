from datetime import date

from pydantic import BaseModel, Field


class DocumentVerificationRequest(BaseModel):
    cni: str = Field(min_length=1)
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)

    hospitalization_number: str = Field(
        min_length=1
    )

    service_id: str

    admission_date: date

    discharge_date: date | None = None