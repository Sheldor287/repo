from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, String, UniqueConstraint
from app.models.mbse.relationship import Relationship
from app.models.mbse.element import Element
from app.database import Base
from uuid import uuid4

class Semantic(Base):
    __tablename__ = "semantic_relationships"

    __table_args__ = (
        UniqueConstraint(
            "source_element_uuid",
            "relationship_uuid",
            "target_element_uuid",
            name="uq_semantic_triple",
        ),
    )

    # Identifier for this specific semantic triple.
    semantic_uuid: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Subject / source element.
    source_element_uuid: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("elements.element_uuid"),
        nullable=False,
        index=True,
    )

    # Predicate / relationship type.
    relationship_uuid: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("relationships.relationship_uuid"),
        nullable=False,
        index=True,
    )

    # Object / target element.
    target_element_uuid: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("elements.element_uuid"),
        nullable=False,
        index=True,
    )

    # ORM navigation.
    source_element: Mapped["Element"] = relationship(
        back_populates="outgoing_semantics",
        foreign_keys=[source_element_uuid],
    )

    relationship_type: Mapped["Relationship"] = relationship(
        back_populates="semantics",
    )

    target_element: Mapped["Element"] = relationship(
        back_populates="incoming_semantics",
        foreign_keys=[target_element_uuid],
    )

    def __repr__(self) -> str:
        return (
            f"Semantic("
            f"semantic_uuid={self.semantic_uuid!r}, "
            f"source={self.source_element_uuid!r}, "
            f"relationship={self.relationship_uuid!r}, "
            f"target={self.target_element_uuid!r})"
        )