import uuid

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    String,
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.db.session import Base


class DocumentAIResult(Base):

    __tablename__ = "document_ai_results"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id"),
        nullable=False,
        unique=True,
    )

    cni: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    first_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    last_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    hospitalization_number: Mapped[
        str | None
    ] = mapped_column(
        String(100),
        nullable=True,
    )

    service_name: Mapped[
        str | None
    ] = mapped_column(
        String(100),
        nullable=True,
    )

    admission_date: Mapped[
        date | None
    ] = mapped_column(
        Date,
        nullable=True,
    )

    discharge_date: Mapped[
        date | None
    ] = mapped_column(
        Date,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )