from __future__ import annotations

import csv
import hashlib
import io
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.enum_objects import GovernanceStatus, ValidationStatus
from app.models.ingest import StagingRecord, StagingUpload

router = APIRouter(prefix="/api/ingest", tags=["ingest"])

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
        "file_hash": upload.file_hash,
    }
