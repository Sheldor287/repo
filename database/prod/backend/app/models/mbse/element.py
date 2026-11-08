from __future__ import annotations
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text
from app.database import Base
from uuid import uuid4

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.mbse.semantic import Semantic

class Element(Base):
    __tablename__ = "elements"
    __table_args__ = {"schema": "test"}

    # Canonical identifier for this element across all models.
    element_uuid: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )
    # Human-readable identifier or name.
    name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    # Definition or description of the element.
    definition: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    # Semantic relationships in which this element is the source.
    outgoing_semantics: Mapped[list["Semantic"]] = relationship(
        back_populates="source_element",
        foreign_keys="Semantic.source_element_uuid",
    )
    # Semantic relationships in which this element is the target.
    incoming_semantics: Mapped[list["Semantic"]] = relationship(
        back_populates="target_element",
        foreign_keys="Semantic.target_element_uuid",
    )
    def __repr__(self) -> str:
        return f"Element(element_uuid={self.element_uuid!r}, name={self.name!r})"