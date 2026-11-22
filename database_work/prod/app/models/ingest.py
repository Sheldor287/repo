from __future__ import annotations
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, Text, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from uuid import UUID

from .database import Base
from .enum_objects import GovernanceStatus, PromotionStatus, ValidationStatus


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

    # Legacy validation-status column retained for the original CSV contract.
    # New workflows use the three explicit status columns below.
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

    validation_status: Mapped[ValidationStatus] = mapped_column(
        Enum(ValidationStatus, native_enum=False), nullable=False,
        default=ValidationStatus.PENDING,
    )
    governance_status: Mapped[GovernanceStatus] = mapped_column(
        Enum(GovernanceStatus, native_enum=False), nullable=False,
        default=GovernanceStatus.PENDING,
    )
    promotion_status: Mapped[PromotionStatus] = mapped_column(
        Enum(PromotionStatus, native_enum=False), nullable=False,
        default=PromotionStatus.NOT_PROMOTED,
    )

    domain_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_system: Mapped[str | None] = mapped_column(Text, nullable=True)
    contract_version: Mapped[str | None] = mapped_column(Text, nullable=True)

    decisions: Mapped[list["GovernanceDecision"]] = relationship(
        back_populates="upload",
        order_by="GovernanceDecision.decided_at",
    )

    validation_runs: Mapped[list["ValidationRun"]] = relationship(
        back_populates="upload",
        order_by="ValidationRun.run_number",
    )

    records: Mapped[list["StagingRecord"]] = relationship(
        back_populates="upload",
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

    source_record_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_errors: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    upload: Mapped["StagingUpload"] = relationship(
        back_populates="records",
    )


class ValidationRun(Base):
    """Versioned evidence for one validation execution against a batch."""

    __tablename__ = "validation_run"
    __table_args__ = (
        UniqueConstraint("upload_uuid", "run_number", name="uq_validation_run_upload_number"),
    )

    upload_uuid: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("staging_upload.uuid"), nullable=False
    )
    run_number: Mapped[int] = mapped_column(Integer, nullable=False)
    contract_version: Mapped[str] = mapped_column(Text, nullable=False)
    validator_version: Mapped[str] = mapped_column(Text, nullable=False)
    result_status: Mapped[ValidationStatus] = mapped_column(
        Enum(ValidationStatus, native_enum=False), nullable=False
    )
    valid_count: Mapped[int] = mapped_column(Integer, nullable=False)
    invalid_count: Mapped[int] = mapped_column(Integer, nullable=False)
    errors: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    upload: Mapped["StagingUpload"] = relationship(back_populates="validation_runs")


class DomainRecord(Base):
    """Versioned notional ERP representation promoted from a governed batch."""

    __tablename__ = "domain_record"
    __table_args__ = (
        UniqueConstraint(
            "domain_key", "entity_type", "source_system", "source_record_id", "revision",
            name="uq_domain_record_source_revision",
        ),
    )

    domain_key: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    source_record_id: Mapped[str] = mapped_column(Text, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    program_code: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_system: Mapped[str] = mapped_column(Text, nullable=False)
    authority_status: Mapped[str] = mapped_column(Text, nullable=False, default="UNASSIGNED")
    authoritative_system: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_upload_uuid: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("staging_upload.uuid"), nullable=False
    )
    promoted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class GovernanceDecision(Base):
    """Immutable batch-level governance decision for a staged upload."""

    __tablename__ = "governance_decision"

    upload_uuid: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("staging_upload.uuid"), nullable=False
    )
    decision: Mapped[GovernanceStatus] = mapped_column(
        Enum(GovernanceStatus, native_enum=False), nullable=False
    )
    decided_by: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    upload: Mapped["StagingUpload"] = relationship(back_populates="decisions")
