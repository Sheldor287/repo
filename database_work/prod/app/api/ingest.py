from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.domain_catalog import CURRENT_CONTRACT_VERSION, entity_domain
from app.models.enum_objects import GovernanceStatus, PromotionStatus, ValidationStatus
from app.models.ingest import (
    StagingRecord,
    StagingUpload,
    ValidationRun,
)
from app.services.domain_validation import validate_domain_record
from app.services.govern import record_governance_decision

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


class GovernanceDecisionInput(BaseModel):
    decision: str
    decided_by: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=4000)


class DomainRecordInput(BaseModel):
    source_record_id: str = Field(min_length=1, max_length=300)
    data: dict[str, Any]


class DomainBatchInput(BaseModel):
    source_system: str = Field(min_length=1, max_length=200)
    contract_version: str = Field(default="1.0", min_length=1, max_length=100)
    records: list[DomainRecordInput]

EXPECTED_COLUMNS = [
    "uuid",
    "name",
    "phone",
    "job",
    "vin",
    "city",
    "governance_status",
    "created_at",
]
DOMAIN_VALIDATOR_VERSION = "catalog-1.0"


@router.post("/domain/{entity_type}", status_code=201)
def stage_domain_batch(
    entity_type: str,
    payload: DomainBatchInput,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    domain_key = entity_domain(entity_type)
    if domain_key is None:
        raise HTTPException(status_code=404, detail="Unknown domain entity type")
    if not payload.source_system.strip() or not payload.contract_version.strip():
        raise HTTPException(status_code=400, detail="source_system and contract_version must not be blank")
    if payload.contract_version != CURRENT_CONTRACT_VERSION:
        raise HTTPException(status_code=400, detail=f"Unsupported contract_version; use {CURRENT_CONTRACT_VERSION}")
    if not payload.records:
        raise HTTPException(status_code=400, detail="At least one record is required")

    source_ids = [item.source_record_id.strip() for item in payload.records]
    duplicate_ids = {value for value, count in Counter(source_ids).items() if count > 1}
    staged_rows: list[tuple[DomainRecordInput, list[str]]] = []
    for item, source_id in zip(payload.records, source_ids):
        errors = validate_domain_record(
            db,
            entity_type,
            item.data,
            payload.source_system.strip(),
            source_id,
        )
        if not source_id:
            errors.append("source_record_id: value must not be blank")
        if source_id in duplicate_ids:
            errors.append(f"source_record_id: duplicate value in batch ({source_id})")
        staged_rows.append((item, errors))
    # Referential checks use a read transaction. Start the atomic staging write
    # in a clean transaction after those reads complete.
    db.rollback()

    canonical_payload = {
        "entity_type": entity_type,
        "source_system": payload.source_system.strip(),
        "contract_version": payload.contract_version.strip(),
        "records": [
            {"source_record_id": item.source_record_id, "data": item.data}
            for item in payload.records
        ],
    }
    content = json.dumps(canonical_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    has_errors = any(errors for _, errors in staged_rows)
    upload = StagingUpload(
        filename=f"{entity_type}.json",
        status=ValidationStatus.INVALID if has_errors else ValidationStatus.VALIDATED,
        validation_status=ValidationStatus.INVALID if has_errors else ValidationStatus.VALIDATED,
        governance_status=GovernanceStatus.PENDING,
        promotion_status=PromotionStatus.NOT_PROMOTED,
        record_count=len(staged_rows),
        file_hash=hashlib.sha256(content).hexdigest(),
        domain_key=domain_key,
        entity_type=entity_type,
        source_system=payload.source_system.strip(),
        contract_version=payload.contract_version,
    )
    try:
        with db.begin():
            db.add(upload)
            db.flush()
            for row_number, (item, errors) in enumerate(staged_rows, start=1):
                db.add(
                    StagingRecord(
                        upload_uuid=upload.uuid,
                        record_uuid=uuid4(),
                        row_number=row_number,
                        validation_status=ValidationStatus.INVALID if errors else ValidationStatus.VALIDATED,
                        raw_data=item.data,
                        source_record_id=item.source_record_id.strip(),
                        validation_errors=errors or None,
                    )
                )
            db.add(
                ValidationRun(
                    upload_uuid=upload.uuid,
                    run_number=1,
                    contract_version=payload.contract_version,
                    validator_version=DOMAIN_VALIDATOR_VERSION,
                    result_status=ValidationStatus.INVALID if has_errors else ValidationStatus.VALIDATED,
                    valid_count=sum(1 for _, errors in staged_rows if not errors),
                    invalid_count=sum(1 for _, errors in staged_rows if errors),
                    errors=[
                        {"row_number": row_number, "errors": errors}
                        for row_number, (_, errors) in enumerate(staged_rows, start=1)
                        if errors
                    ],
                )
            )
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Could not stage the domain batch") from exc

    return {
        "upload_uuid": str(upload.uuid),
        "domain": domain_key,
        "entity_type": entity_type,
        "record_count": upload.record_count,
        "status": upload.status.value,
        "validation_status": upload.validation_status.value,
        "governance_status": upload.governance_status.value,
        "promotion_status": upload.promotion_status.value,
        "file_hash": upload.file_hash,
        "validation_errors": [
            {"row_number": row_number, "source_record_id": item.source_record_id, "errors": errors}
            for row_number, (item, errors) in enumerate(staged_rows, start=1)
            if errors
        ],
    }


def parse_csv(content: bytes) -> list[dict[str, str]]:
    """Parse and validate the prototype CSV contract before writing anything."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded") from exc

    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames != EXPECTED_COLUMNS:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "CSV columns do not match the expected contract",
                "expected_columns": EXPECTED_COLUMNS,
                "received_columns": reader.fieldnames,
            },
        )

    records: list[dict[str, str]] = []
    seen_uuids: set[UUID] = set()
    for row_number, row in enumerate(reader, start=2):
        if None in row or any(value is None for value in row.values()):
            raise HTTPException(
                status_code=400,
                detail=f"Row {row_number} has a different number of columns",
            )
        values = {column: (row[column] or "").strip() for column in EXPECTED_COLUMNS}
        missing = [column for column, value in values.items() if not value]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Row {row_number} has empty values for: {', '.join(missing)}",
            )

        try:
            record_uuid = UUID(values["uuid"])
        except ValueError as exc:
            raise HTTPException(
                status_code=400, detail=f"Row {row_number} has an invalid UUID"
            ) from exc
        if record_uuid in seen_uuids:
            raise HTTPException(
                status_code=400,
                detail=f"Row {row_number} duplicates UUID {record_uuid}",
            )
        seen_uuids.add(record_uuid)

        if values["governance_status"] not in GovernanceStatus.__members__:
            allowed = ", ".join(GovernanceStatus.__members__)
            raise HTTPException(
                status_code=400,
                detail=f"Row {row_number} has invalid governance_status; use: {allowed}",
            )
        try:
            datetime.fromisoformat(values["created_at"])
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Row {row_number} has an invalid created_at timestamp",
            ) from exc
        records.append(values)

    if not records:
        raise HTTPException(status_code=400, detail="CSV contains no data rows")
    return records


@router.post("/upload")
async def upload_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    filename = file.filename or ""
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="CSV file is required")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="File content is required")
    records = parse_csv(content)

    upload = StagingUpload(
        filename=filename,
        status=ValidationStatus.VALIDATED,
        validation_status=ValidationStatus.VALIDATED,
        record_count=len(records),
        file_hash=hashlib.sha256(content).hexdigest(),
    )
    try:
        with db.begin():
            db.add(upload)
            db.flush()
            for row_number, values in enumerate(records, start=2):
                db.add(
                    StagingRecord(
                        upload_uuid=upload.uuid,
                        record_uuid=UUID(values["uuid"]),
                        row_number=row_number,
                        validation_status=ValidationStatus.VALIDATED,
                        raw_data=values,
                    )
                )
            db.add(
                ValidationRun(
                    upload_uuid=upload.uuid,
                    run_number=1,
                    contract_version="legacy-csv-8-column-v1",
                    validator_version="csv-contract-v1",
                    result_status=ValidationStatus.VALIDATED,
                    valid_count=len(records),
                    invalid_count=0,
                    errors=[],
                )
            )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="The upload conflicts with an existing staged record",
        ) from exc

    return {
        "upload_uuid": str(upload.uuid),
        "filename": upload.filename,
        "record_count": upload.record_count,
        "status": upload.status.value,
        "validation_status": upload.validation_status.value,
        "governance_status": upload.governance_status.value,
        "file_hash": upload.file_hash,
    }


@router.get("/uploads")
def list_uploads(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    uploads = db.scalars(
        select(StagingUpload)
        .options(selectinload(StagingUpload.decisions))
        .options(selectinload(StagingUpload.records))
        .options(selectinload(StagingUpload.validation_runs))
        .order_by(StagingUpload.uploaded_at.desc())
    ).all()
    return [
        {
            "upload_uuid": str(upload.uuid),
            "filename": upload.filename,
            "record_count": upload.record_count,
            "status": upload.status.value,
            "validation_status": upload.validation_status.value,
            "governance_status": upload.governance_status.value,
            "promotion_status": upload.promotion_status.value,
            "uploaded_at": upload.uploaded_at.isoformat(),
            "file_hash": upload.file_hash,
            "domain": upload.domain_key,
            "entity_type": upload.entity_type,
            "source_system": upload.source_system,
            "validation_errors": [
                {
                    "row_number": row.row_number,
                    "source_record_id": row.source_record_id,
                    "errors": row.validation_errors or [],
                }
                for row in upload.records
                if row.validation_errors
            ],
            "validation_runs": [
                {
                    "run_number": run.run_number,
                    "contract_version": run.contract_version,
                    "validator_version": run.validator_version,
                    "result_status": run.result_status.value,
                    "valid_count": run.valid_count,
                    "invalid_count": run.invalid_count,
                    "executed_at": run.executed_at.isoformat(),
                    "errors": run.errors,
                }
                for run in upload.validation_runs
            ],
            "decisions": [
                {
                    "decision": item.decision.value,
                    "decided_by": item.decided_by,
                    "reason": item.reason,
                    "decided_at": item.decided_at.isoformat(),
                }
                for item in upload.decisions
            ],
        }
        for upload in uploads
    ]


@router.post("/uploads/{upload_uuid}/governance")
def decide_upload(
    upload_uuid: UUID,
    payload: GovernanceDecisionInput,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        decision = GovernanceStatus(payload.decision.upper())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="decision must be APPROVED or REJECTED") from exc
    if decision not in (GovernanceStatus.APPROVED, GovernanceStatus.REJECTED):
        raise HTTPException(status_code=400, detail="decision must be APPROVED or REJECTED")

    upload = db.get(StagingUpload, upload_uuid)
    if upload is None:
        raise HTTPException(status_code=404, detail="Staged upload not found")
    try:
        record = record_governance_decision(
            db,
            upload,
            decision,
            payload.decided_by,
            payload.reason,
        )
    except ValueError as exc:
        db.rollback()
        detail = str(exc)
        status_code = 400 if "required" in detail.lower() else 409
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Governance promotion conflicted with an existing record revision") from exc
    return {
        "upload_uuid": str(upload.uuid),
        "status": upload.status.value,
        "validation_status": upload.validation_status.value,
        "governance_status": upload.governance_status.value,
        "promotion_status": upload.promotion_status.value,
        "decision": record.decision.value,
        "decided_by": record.decided_by,
        "reason": record.reason,
        "decided_at": record.decided_at.isoformat(),
    }
