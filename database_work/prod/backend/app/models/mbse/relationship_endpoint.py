from __future__ import annotations
from uuid import UUID
from sqlalchemy import ForeignKey, Index, Integer, Text, UniqueConstraint, text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship
from ..database import MBSE
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .instance_definition import InstanceDefinition
    from .object_relationship import ObjectRelationship


class RelationshipEndpoint(MBSE):
    __tablename__ = "relationship_endpoints"
    __table_args__ = (
        UniqueConstraint(
            "relationship_uuid",
            "instance_uuid",
            "endpoint_role",
            "ordinal",
            name="uq_relationship_endpoint",
        ),
        Index(
            "idx_relationship_endpoint_relationship_uuid",
            "relationship_uuid",
        ),
        Index(
            "idx_relationship_endpoint_instance_uuid",
            "instance_uuid",
        ),
    )

    relationship_uuid: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "object_relationships.uuid",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    instance_uuid: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "instance_definition.uuid",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    endpoint_role: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    ordinal: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )

    multiplicity_lower: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    multiplicity_upper: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    role_name: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    relationship: Mapped["ObjectRelationship"] = orm_relationship(
        back_populates="endpoints",
    )

    instance: Mapped["InstanceDefinition"] = orm_relationship(
        back_populates="endpoints",
    )