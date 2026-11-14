from __future__ import annotations
from sqlalchemy import Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship
from ..database import MBSE
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .applied_stereotype import AppliedStereotype


class Stereotype(MBSE):
    __tablename__ = "stereotypes"
    __table_args__ = (
        UniqueConstraint(
            "profile_name",
            "stereotype",
            name="uq_stereotype_profile_name",
        ),
    )

    stereotype: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    definition: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    profile_name: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    base_metaclass: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    applications: Mapped[list["AppliedStereotype"]] = orm_relationship(
        back_populates="stereotype",
    )