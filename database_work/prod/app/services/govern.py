from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enum_objects import GovernanceStatus, PromotionStatus, ValidationStatus
from app.models.ingest import DomainRecord, GovernanceDecision, StagingRecord, StagingUpload


def resolve_authority(db: Session, domain_key: str, entity_type: str) -> tuple[str, str | None]:
    """Resolve approved authority metadata without inferring from storage."""
    rows = db.scalars(
        select(DomainRecord)
        .where(
            DomainRecord.domain_key == "integration_governance",
            DomainRecord.entity_type == "data_authority",
        )
        .order_by(DomainRecord.promoted_at.desc())
    ).all()
    latest_by_source: dict[tuple[str, str], DomainRecord] = {}
    for row in rows:
        key = (row.source_system, row.source_record_id)
        if key not in latest_by_source or row.revision > latest_by_source[key].revision:
            latest_by_source[key] = row
    mappings = [
        row.data
        for row in latest_by_source.values()
        if row.data.get("data_domain") in (domain_key, entity_type)
    ]
    today_utc = datetime.now(timezone.utc).date()
    mappings = [
        item
        for item in mappings
        if (not item.get("effective_date") or datetime.fromisoformat(item["effective_date"]).date() <= today_utc)
        and (not item.get("end_date") or datetime.fromisoformat(item["end_date"]).date() >= today_utc)
    ]
    bindings = {
        (
            str(item.get("authoritative_system", "")).strip(),
            str(item.get("governance_authority", "")).strip(),
        )
        for item in mappings
        if item.get("authoritative_system")
    }
    if len(bindings) > 1:
        return "CONFLICT", None
    if not bindings:
        return "UNASSIGNED", None
    authoritative_system, _ = bindings.pop()
    erp_code = os.getenv("ERP_SYSTEM_CODE", "ERP").strip().casefold()
    status = "ERP_AUTHORITATIVE" if authoritative_system.casefold() == erp_code else "EXTERNAL_AUTHORITATIVE"
    return status, authoritative_system


def promote_staged_upload(db: Session, upload: StagingUpload) -> None:
    """Append all valid staged rows as one governed promotion transaction."""
    if not upload.domain_key or not upload.entity_type:
        return
    staged_records = db.scalars(
        select(StagingRecord)
        .where(StagingRecord.upload_uuid == upload.uuid)
        .order_by(StagingRecord.row_number)
    ).all()
    if any(row.validation_status != ValidationStatus.VALIDATED for row in staged_records):
        raise ValueError("Batch contains records that did not pass validation")

    authority_status, authoritative_system = resolve_authority(db, upload.domain_key, upload.entity_type)
    for row in staged_records:
        if not row.source_record_id or not row.raw_data:
            raise ValueError("Domain batch record is missing identity or data")
        prior_revision = db.scalar(
            select(func.max(DomainRecord.revision)).where(
                DomainRecord.domain_key == upload.domain_key,
                DomainRecord.entity_type == upload.entity_type,
                DomainRecord.source_system == upload.source_system,
                DomainRecord.source_record_id == row.source_record_id,
            )
        )
        data = row.raw_data
        display_name = next(
            (
                str(data[key])
                for key in (
                    "name", "title", "program_code", "contract_number", "asset_tag",
                    "item_code", "transaction_id", "requirement_id", "part_number",
                )
                if data.get(key)
            ),
            row.source_record_id,
        )
        db.add(
            DomainRecord(
                domain_key=upload.domain_key,
                entity_type=upload.entity_type,
                source_record_id=row.source_record_id,
                revision=(prior_revision or 0) + 1,
                program_code=data.get("program_code"),
                display_name=display_name,
                data=data,
                source_system=upload.source_system or "unspecified",
                authority_status=authority_status,
                authoritative_system=authoritative_system,
                source_upload_uuid=upload.uuid,
            )
        )
    upload.promotion_status = PromotionStatus.PROMOTED


def record_governance_decision(
    db: Session,
    upload: StagingUpload,
    decision: GovernanceStatus,
    decided_by: str,
    reason: str,
) -> GovernanceDecision:
    """Apply one batch decision and promote approved domain data atomically."""
    is_domain_batch = upload.domain_key is not None
    if is_domain_batch:
        if upload.validation_status != ValidationStatus.VALIDATED:
            raise ValueError("Only validated uploads can receive a governance decision")
        if upload.governance_status != GovernanceStatus.PENDING:
            raise ValueError("This batch already has a governance decision")
    elif upload.status != ValidationStatus.VALIDATED:
        raise ValueError("Only validated uploads can receive a governance decision")

    reviewer = decided_by.strip()
    decision_reason = reason.strip()
    if not reviewer or not decision_reason:
        raise ValueError("Reviewer name and decision reason are required")

    event = GovernanceDecision(
        upload_uuid=upload.uuid,
        decision=decision,
        decided_by=reviewer,
        reason=decision_reason,
    )
    upload.governance_status = decision
    db.add(event)
    try:
        if decision == GovernanceStatus.APPROVED and is_domain_batch:
            promote_staged_upload(db, upload)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(event)
    return event
