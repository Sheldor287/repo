from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import Text, UniqueConstraint, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship
from ..database import MBSE
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .model_version import ModelVersion


class EngineeringModel(MBSE):
    __tablename__ = "engineering_model"
    __table_args__ = (
        UniqueConstraint("name", name="uq_engineering_model_name"),
    )

    name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    source_tool: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    source_format: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    versions: Mapped[list["ModelVersion"]] = orm_relationship(
        back_populates="model",
        cascade="all, delete-orphan",
    )