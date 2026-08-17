from datetime import date

from pydantic import BaseModel


class AIExtractionResult(BaseModel):

    cni: str | None = None

    first_name: str | None = None

    last_name: str | None = None

    hospitalization_number: str | None = None

    service: str | None = None

    admission_date: date | None = None

    discharge_date: date | None = None