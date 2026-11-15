from __future__ import annotations
from datetime import datetime
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import ForeignKey, Index, Text, DateTime, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship
from ..database import MBSE
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .engineering_model import EngineeringModel
    from .instance_definition import InstanceDefinition
    from .object_relationship import ObjectRelationship


class ModelVersion(MBSE):
    __tablename__ = "model_version"
    __table_args__ = (
        UniqueConstraint(
            "model_uuid",
            "version_label",
            name="uq_model_version_model_label",
        ),
        Index(
            "idx_model_version_model_uuid",
            "model_uuid",
        ),
    )

    model_uuid: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "engineering_model.uuid",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    version_label: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    parent_version_uuid: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "model_version.uuid",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    source_filename: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    source_hash: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    imported_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=True,
    )

    model: Mapped["EngineeringModel"] = orm_relationship(
        back_populates="versions",
    )

    parent_version: Mapped["ModelVersion | None"] = orm_relationship(
        remote_side="ModelVersion.uuid",
        back_populates="child_versions",
    )

    child_versions: Mapped[list["ModelVersion"]] = orm_relationship(
        back_populates="parent_version",
    )

    instances: Mapped[list["InstanceDefinition"]] = orm_relationship(
        back_populates="model_version",
        cascade="all, delete-orphan",
    )

    relationships: Mapped[list["ObjectRelationship"]] = orm_relationship(
        back_populates="model_version",
        cascade="all, delete-orphan",
    )