import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Hospitalization(Base):
    __tablename__ = "hospitalizations"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    hospitalization_number: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("patients.id"),
        nullable=False,
    )

    service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("services.id"),
        nullable=False,
    )

    admission_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    discharge_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )