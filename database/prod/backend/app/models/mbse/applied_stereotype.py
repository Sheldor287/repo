from __future__ import annotations
from uuid import UUID, uuid4
from sqlalchemy import CheckConstraint, ForeignKey, Index, JSON, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship
from app.database import Base
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.mbse.instance_definition import InstanceDefinition
    from app.models.mbse.object_relationship import ObjectRelationship
    from app.models.mbse.stereotype import Stereotype


class AppliedStereotype(Base):
    __tablename__ = "applied_stereotypes"
    __table_args__ = (
        CheckConstraint(
            "target_type IN ('instance', 'relationship')",
            name="ck_applied_stereotype_target_type",
        ),
        CheckConstraint(
            """
            (
                target_type = 'instance'
                AND instance_uuid IS NOT NULL
                AND relationship_uuid IS NULL
            )
            OR
            (
                target_type = 'relationship'
                AND relationship_uuid IS NOT NULL
                AND instance_uuid IS NULL
            )
            """,
            name="ck_applied_stereotype_target",
        ),
        Index(
            "idx_applied_stereotype_instance_uuid",
            "instance_uuid",
        ),
        Index(
            "idx_applied_stereotype_relationship_uuid",
            "relationship_uuid",
        ),
        Index(
            "idx_applied_stereotype_stereotype_uuid",
            "stereotype_uuid",
        ),
    )

    uuid: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    stereotype_uuid: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "stereotypes.uuid",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    target_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    instance_uuid: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "instance_definition.uuid",
            ondelete="CASCADE",
        ),
        nullable=True,
    )

    relationship_uuid: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "object_relationships.uuid",
            ondelete="CASCADE",
        ),
        nullable=True,
    )

    source_identifier: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    tagged_values: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    stereotype: Mapped["Stereotype"] = orm_relationship(
        back_populates="applications",
    )

    instance: Mapped["InstanceDefinition | None"] = orm_relationship()

    relationship: Mapped["ObjectRelationship | None"] = orm_relationship()