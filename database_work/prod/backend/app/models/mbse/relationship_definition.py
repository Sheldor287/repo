from __future__ import annotations
from sqlalchemy import Boolean, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship
from ..database import MBSE, GovernanceBase
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .object_relationship import ObjectRelationship


class RelationshipDefinition(MBSE, GovernanceBase):
    __tablename__ = "relationship_definition"
    __table_args__ = (
        UniqueConstraint(
            "relationship",
            name="uq_relationship_definition_relationship",
        ),
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

    instances: Mapped[list["ObjectRelationship"]] = orm_relationship(
        back_populates="relationship_definition",
    )