from __future__ import annotations
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import ForeignKey, Index, Text, TIMESTAMP, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship
from app.database import Base
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.mbse.engineering_model import EngineeringModel
    from app.models.mbse.instance_definition import InstanceDefinition
    from app.models.mbse.object_relationship import ObjectRelationship


class ModelVersion(Base):
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

    uuid: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
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

    imported_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    classification: Mapped[str | None] = mapped_column(
        Text,
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