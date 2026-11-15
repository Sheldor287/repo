from __future__ import annotations
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, Text, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from uuid import UUID

from .database import Base
from .enum_objects import ValidationStatus


class StagingUpload(Base):
    """Represents an upload session, not a file upload"""
    __tablename__ = "staging_upload"

    filename: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    status: Mapped[ValidationStatus] = mapped_column(
        Enum(ValidationStatus, native_enum=False),
        nullable=False,
        default=ValidationStatus.PENDING,
    )

    record_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    file_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    records: Mapped[list["StagingRecord"]] = relationship(
        back_populates="upload",
        cascade="all, delete-orphan",
    )


class StagingRecord(Base):
    __tablename__ = "staging_record"
    __table_args__ = (
        UniqueConstraint("upload_uuid", "record_uuid", name="uq_staging_record_upload_record"),
    )
    """
    Represents a single record within a staging upload
    
    UUIDs:
    uuid (from Base) -- Primary key
    upload_uuid -- Foreign key to staging_upload.uuid
    record_uuid -- Unique identifier for the record
    """

    upload_uuid: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "staging_upload.uuid",
        ),
        nullable=False,
    )

    record_uuid: Mapped[UUID] = mapped_column(
        Uuid,
        nullable=False,
    )

    row_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    validation_status: Mapped[ValidationStatus] = mapped_column(
        Enum(ValidationStatus, native_enum=False),
        nullable=False,
        default=ValidationStatus.PENDING,
    )

    raw_data: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )

    upload: Mapped["StagingUpload"] = relationship(
        back_populates="records",
    )
