from __future__ import annotations
from uuid import UUID, uuid4
from sqlalchemy import Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship
from app.database import Base
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.mbse.applied_stereotype import AppliedStereotype


class Stereotype(Base):
    __tablename__ = "stereotypes"
    __table_args__ = (
        UniqueConstraint(
            "profile_name",
            "stereotype",
            name="uq_stereotype_profile_name",
        ),
    )

    uuid: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
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