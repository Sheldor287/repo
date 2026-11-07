from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.mbse.semantic import Semantic
from sqlalchemy import String, Text
from app.database import Base
from uuid import uuid4

class Relationship(Base):
    __tablename__ = "relationships"

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
    semantics: Mapped[list["Semantic"]] = relationship(
        back_populates="relationship",
    )

    def __repr__(self) -> str:
        return (
            f"Relationship("
            f"relationship_uuid={self.relationship_uuid!r}, "
            f"name={self.name!r})"
        )