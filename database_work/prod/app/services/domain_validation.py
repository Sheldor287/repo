from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain_catalog import REFERENCE_RULES, validate_record
from app.models.ingest import DomainRecord


def validate_domain_record(
    db: Session,
    entity_type: str,
    data: dict[str, Any],
    source_system: str,
    source_record_id: str,
) -> list[str]:
    """Apply contract, identity, business-key, and selected relationship rules."""
    errors = validate_record(entity_type, data)
    if errors:
        return errors
    cache: dict[str, list[DomainRecord]] = {}

    def current_records(target_entity: str) -> list[DomainRecord]:
        if target_entity not in cache:
            rows = db.scalars(
                select(DomainRecord)
                .where(DomainRecord.entity_type == target_entity)
                .order_by(DomainRecord.promoted_at.desc())
            ).all()
            latest: dict[tuple[str, str], DomainRecord] = {}
            for row in rows:
                key = (row.source_system, row.source_record_id)
                if key not in latest or row.revision > latest[key].revision:
                    latest[key] = row
            cache[target_entity] = list(latest.values())
        return cache[target_entity]

    for field, (target_entity, target_field) in REFERENCE_RULES.get(entity_type, {}).items():
        value = data.get(field)
        if value is None or value == "":
            continue
        if not any(row.data.get(target_field) == value for row in current_records(target_entity)):
            errors.append(f"{field}: no promoted {target_entity} has {target_field}={value!r}")

    if entity_type == "inventory_transaction":
        # Transactions are business events; a repeated source identity cannot
        # revise an existing event.
        if db.scalar(
            select(DomainRecord.uuid).where(
                DomainRecord.entity_type == entity_type,
                DomainRecord.source_system == source_system,
                DomainRecord.source_record_id == source_record_id,
            ).limit(1)
        ) is not None:
            errors.append("transaction_id: inventory transactions are immutable; duplicate event identity")

    if entity_type == "domain_relationship":
        for side in ("source", "target"):
            identity = (
                data.get(f"{side}_domain"),
                data.get(f"{side}_entity_type"),
                data.get(f"{side}_system"),
                data.get(f"{side}_record_id"),
            )
            exists = db.scalar(
                select(DomainRecord.uuid).where(
                    DomainRecord.domain_key == identity[0],
                    DomainRecord.entity_type == identity[1],
                    DomainRecord.source_system == identity[2],
                    DomainRecord.source_record_id == identity[3],
                ).limit(1)
            )
            if exists is None:
                errors.append(f"{side}: referenced promoted record representation does not exist")

    if entity_type in ("user_identity", "workforce_assignment"):
        person_source_id = data.get("person_source_record_id") or data.get("person_source_id")
        person_source_system = data.get("person_source_system")
        person_id_field = "person_source_record_id" if entity_type == "user_identity" else "person_source_id"
        if person_source_id and person_source_system:
            exists = db.scalar(
                select(DomainRecord.uuid).where(
                    DomainRecord.entity_type == "person",
                    DomainRecord.source_record_id == person_source_id,
                    DomainRecord.source_system == person_source_system,
                ).limit(1)
            )
            if exists is None:
                errors.append(f"{person_id_field}: no promoted Person matches this source identity")
        elif person_source_id or person_source_system:
            errors.append(f"{person_id_field}: person source references require both source system and record ID")

    if entity_type == "external_identifier":
        try:
            target_uuid = UUID(data.get("erp_record_uuid", ""))
        except (TypeError, ValueError):
            target_uuid = None
        if target_uuid is None or db.scalar(
            select(DomainRecord.uuid).where(
                DomainRecord.uuid == target_uuid,
                DomainRecord.entity_type == data.get("erp_entity_type"),
            ).limit(1)
        ) is None:
            errors.append("erp_record_uuid: no promoted ERP record matches this UUID and entity type")
        existing_mappings = db.scalars(
            select(DomainRecord).where(DomainRecord.entity_type == "external_identifier")
        ).all()
        for mapping in existing_mappings:
            existing_data = mapping.data
            if (
                existing_data.get("external_system") == data.get("external_system")
                and existing_data.get("external_id") == data.get("external_id")
                and existing_data.get("erp_record_uuid") != data.get("erp_record_uuid")
            ):
                errors.append("external_id: already maps to a different ERP record")
                break

    return errors
