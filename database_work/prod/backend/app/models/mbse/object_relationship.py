# app/models/mbse/object_relationship.py
from __future__ import annotations
from uuid import UUID
from sqlalchemy import Boolean, ForeignKey, Index, JSON, Text, Uuid, false
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship
from ..database import MBSE
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .instance_definition import InstanceDefinition
    from .model_version import ModelVersion
    from .relationship_definition import RelationshipDefinition
    from .relationship_endpoint import RelationshipEndpoint
    from .relationship_instance_property import RelationshipInstanceProperty

    
class ObjectRelationship(MBSE):
    __tablename__ = "object_relationships"
    __table_args__ = (
        Index(
            "idx_object_relationship_model_version_uuid",
            "model_version_uuid",
        ),
        Index(
            "idx_object_relationship_source_instance_uuid",
            "source_instance_uuid",
        ),
        Index(
            "idx_object_relationship_target_instance_uuid",
            "target_instance_uuid",
        ),
        Index(
            "idx_object_relationship_relationship_definition_uuid",
            "relationship_definition_uuid",
        ),
        Index(
            "uq_object_relationship_source_identifier",
            "model_version_uuid",
            "source_identifier",
            unique=True,
        ),
    )

    model_version_uuid: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "model_version.uuid",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    relationship_definition_uuid: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "relationship_definition.uuid",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    source_instance_uuid: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "instance_definition.uuid",
            ondelete="CASCADE",
        ),
        nullable=True,
    )

    target_instance_uuid: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "instance_definition.uuid",
            ondelete="CASCADE",
        ),
        nullable=True,
    )

    source_identifier: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    relationship_name: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    definition: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    source_payload: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )

    model_version: Mapped["ModelVersion"] = orm_relationship(
        back_populates="relationships",
    )

    relationship_definition: Mapped["RelationshipDefinition"] = orm_relationship(
        back_populates="instances",
    )

    source_instance: Mapped["InstanceDefinition | None"] = orm_relationship(
        foreign_keys=[source_instance_uuid],
        back_populates="source_relationships",
    )

    target_instance: Mapped["InstanceDefinition | None"] = orm_relationship(
        foreign_keys=[target_instance_uuid],
        back_populates="target_relationships",
    )

    endpoints: Mapped[list["RelationshipEndpoint"]] = orm_relationship(
        back_populates="relationship",
        cascade="all, delete-orphan",
    )

    properties: Mapped[list["RelationshipInstanceProperty"]] = orm_relationship(
        back_populates="relationship",
        cascade="all, delete-orphan",
    )