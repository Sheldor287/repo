from __future__ import annotations
from uuid import UUID
from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship
from ..database import MBSE
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .object_definition import ObjectDefinition


class ClassTaxonomy(MBSE):
    __tablename__ = "class_taxonomy"
    __table_args__ = (
        UniqueConstraint(
            "class_uuid",
            "subclass_uuid",
            name="uq_class_taxonomy",
        ),
        CheckConstraint(
            "class_uuid <> subclass_uuid",
            name="ck_class_taxonomy_no_self_reference",
        ),
    )

    class_uuid: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "object_definition.uuid",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    subclass_uuid: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "object_definition.uuid",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    class_definition: Mapped["ObjectDefinition"] = orm_relationship(
        foreign_keys=[class_uuid],
        back_populates="child_taxonomy",
    )

    subclass: Mapped["ObjectDefinition"] = orm_relationship(
        foreign_keys=[subclass_uuid],
        back_populates="parent_taxonomy",
    )