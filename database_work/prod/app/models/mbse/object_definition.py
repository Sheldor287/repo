from __future__ import annotations
from sqlalchemy import Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship
from ..database import MBSE
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .instance_definition import InstanceDefinition
    from .class_taxonomy import ClassTaxonomy


class ObjectDefinition(MBSE):
    __tablename__ = "object_definition"
    __table_args__ = (
        UniqueConstraint("object", name="uq_object_definition_object"),
    )

    object: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    definition: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    metaclass: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    instances: Mapped[list["InstanceDefinition"]] = orm_relationship(
        back_populates="object_definition",
    )

    parent_taxonomy: Mapped[list["ClassTaxonomy"]] = orm_relationship(
        foreign_keys="ClassTaxonomy.subclass_uuid",
        back_populates="subclass",
    )

    child_taxonomy: Mapped[list["ClassTaxonomy"]] = orm_relationship(
        foreign_keys="ClassTaxonomy.class_uuid",
        back_populates="class_definition",
    )