from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship
from sqlalchemy import String, Text
from app.database import Base
from uuid import uuid4

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from database.prod.backend.app.models.mbse.depr.semantic import Semantic

class Relationship(Base):
    __tablename__ = "relationships"
    __table_args__ = {"schema": "test"}
    # Identifier for the relationship type.
    relationship_uuid: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    # Human-readable relationship name.
    name: Mapped[str | None] = mapped_column(
        String(255), 
        nullable=True,
        )
    # Definition of the relationship.
    definition: Mapped[str] = mapped_column(
        Text, 
        nullable=False,
        )
    # Semantic triples that use this relationship type.
    semantics: Mapped[list["Semantic"]] = orm_relationship(
        back_populates="relationship_type",
        )

    def __repr__(self) -> str:
        return (
            f"Relationship("
            f"relationship_uuid={self.relationship_uuid!r}, "
            f"name={self.name!r})"
        )