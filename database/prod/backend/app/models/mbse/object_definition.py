from __future__ import annotations
from uuid import UUID, uuid4
from sqlalchemy import Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship
from app.database import Base
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.mbse.instance_definition import InstanceDefinition
    from app.models.mbse.class_taxonomy import ClassTaxonomy


class ObjectDefinition(Base):
    __tablename__ = "object_definition"
    __table_args__ = (
        UniqueConstraint("object", name="uq_object_definition_object"),
    )

    uuid: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=uuid4,
        server_default=text("gen_random_uuid()"),
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

    classification: Mapped[str | None] = mapped_column(
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