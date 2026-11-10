from __future__ import annotations
from uuid import UUID, uuid4
from sqlalchemy import Boolean, Text, UniqueConstraint, text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship
from app.database import Base
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.mbse.engineering_model import EngineeringModel
    from app.models.mbse.instance_definition import InstanceDefinition
    from app.models.mbse.object_relationship import ObjectRelationship


class RelationshipDefinition(Base):
    __tablename__ = "relationship_definition"
    __table_args__ = (
        UniqueConstraint(
            "relationship",
            name="uq_relationship_definition_relationship",
        ),
    )

    uuid: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    relationship: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    definition: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    is_directional: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    classification: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    instances: Mapped[list["ObjectRelationship"]] = orm_relationship(
        back_populates="relationship_definition",
    )