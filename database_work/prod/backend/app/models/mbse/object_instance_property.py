from __future__ import annotations
from uuid import UUID
from sqlalchemy import ForeignKey, Index, JSON, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship
from ..database import MBSE
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .instance_definition import InstanceDefinition


class ObjectInstanceProperty(MBSE):
    __tablename__ = "object_instance_properties"
    __table_args__ = (
        UniqueConstraint(
            "instance_uuid",
            "property_name",
            name="uq_object_instance_property",
        ),
        Index(
            "idx_object_instance_property_instance_uuid",
            "instance_uuid",
        ),
        Index(
            "idx_object_instance_property_property_name",
            "property_name",
        ),
    )

    instance_uuid: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "instance_definition.uuid",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    property_name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    property_value: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    value_type: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    value_json: Mapped[dict | list | None] = mapped_column(
        JSON,
        nullable=True,
    )

    instance: Mapped["InstanceDefinition"] = orm_relationship(
        back_populates="properties",
    )