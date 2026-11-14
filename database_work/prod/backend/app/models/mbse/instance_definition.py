
from __future__ import annotations
from uuid import UUID
from sqlalchemy import Boolean, ForeignKey, Index, JSON, Text, text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship
from ..database import MBSE
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .model_version import ModelVersion
    from .object_definition import ObjectDefinition
    from .object_relationship import ObjectRelationship
    from .relationship_endpoint import RelationshipEndpoint
    from .object_instance_property import ObjectInstanceProperty


class InstanceDefinition(MBSE):
    __tablename__ = "instance_definition"
    __table_args__ = (
        Index(
            "uq_instance_definition_source_identifier",
            "model_version_uuid",
            "source_identifier",
            unique=True,
            postgresql_where=text("source_identifier IS NOT NULL"),
        ),
        Index(
            "idx_instance_definition_model_version_uuid",
            "model_version_uuid",
        ),
        Index(
            "idx_instance_definition_object_definition_uuid",
            "object_definition_uuid",
        ),
        Index(
            "idx_instance_definition_owner_instance_uuid",
            "owner_instance_uuid",
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

    object_definition_uuid: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "object_definition.uuid",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    object: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    definition: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    source_identifier: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    owner_instance_uuid: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "instance_definition.uuid",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    source_path: Mapped[str | None] = mapped_column(
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
        server_default=text("false"),
    )

    model_version: Mapped["ModelVersion"] = orm_relationship(
        back_populates="instances",
    )

    object_definition: Mapped["ObjectDefinition"] = orm_relationship(
        back_populates="instances",
    )

    owner: Mapped["InstanceDefinition | None"] = orm_relationship(
        remote_side="InstanceDefinition.uuid",
        back_populates="owned_instances",
    )

    owned_instances: Mapped[list["InstanceDefinition"]] = orm_relationship(
        back_populates="owner",
    )

    source_relationships: Mapped[list["ObjectRelationship"]] = orm_relationship(
        foreign_keys="ObjectRelationship.source_instance_uuid",
        back_populates="source_instance",
    )

    target_relationships: Mapped[list["ObjectRelationship"]] = orm_relationship(
        foreign_keys="ObjectRelationship.target_instance_uuid",
        back_populates="target_instance",
    )

    endpoints: Mapped[list["RelationshipEndpoint"]] = orm_relationship(
        back_populates="instance",
        cascade="all, delete-orphan",
    )
    
    properties: Mapped[list["ObjectInstanceProperty"]] = orm_relationship(
        back_populates="instance",
        cascade="all, delete-orphan",
    )