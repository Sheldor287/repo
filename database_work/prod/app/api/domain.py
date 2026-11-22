from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.domain_catalog import catalog_response
from app.models.ingest import DomainRecord

router = APIRouter(prefix="/api", tags=["domain data"])


@router.get("/domains")
def list_domains() -> list[dict[str, Any]]:
    return catalog_response()


@router.get("/records")
def list_domain_records(
    domain: str | None = None,
    entity_type: str | None = None,
    program_code: str | None = None,
    history: bool = False,
    limit: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    if history:
        statement = select(DomainRecord)
    else:
        latest = (
            select(
                DomainRecord.domain_key.label("domain_key"),
                DomainRecord.entity_type.label("entity_type"),
                DomainRecord.source_system.label("source_system"),
                DomainRecord.source_record_id.label("source_record_id"),
                func.max(DomainRecord.revision).label("revision"),
            )
            .group_by(
                DomainRecord.domain_key,
                DomainRecord.entity_type,
                DomainRecord.source_system,
                DomainRecord.source_record_id,
            )
            .subquery()
        )
        statement = select(DomainRecord).join(
            latest,
            and_(
                DomainRecord.domain_key == latest.c.domain_key,
                DomainRecord.entity_type == latest.c.entity_type,
                DomainRecord.source_system == latest.c.source_system,
                DomainRecord.source_record_id == latest.c.source_record_id,
                DomainRecord.revision == latest.c.revision,
            ),
        )
    if domain:
        statement = statement.where(DomainRecord.domain_key == domain)
    if entity_type:
        statement = statement.where(DomainRecord.entity_type == entity_type)
    if program_code:
        statement = statement.where(DomainRecord.program_code == program_code)
    rows = db.scalars(statement.order_by(DomainRecord.promoted_at.desc()).limit(limit)).all()
    return [
        {
            "uuid": str(row.uuid),
            "domain": row.domain_key,
            "entity_type": row.entity_type,
            "source_record_id": row.source_record_id,
            "revision": row.revision,
            "program_code": row.program_code,
            "display_name": row.display_name,
            "data": row.data,
            "source_system": row.source_system,
            "authority_status": row.authority_status,
            "authoritative_system": row.authoritative_system,
            "source_upload_uuid": str(row.source_upload_uuid),
            "promoted_at": row.promoted_at.isoformat(),
        }
        for row in rows
    ]


@router.get("/overview")
def get_overview(db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.scalars(select(DomainRecord).order_by(DomainRecord.promoted_at.desc())).all()
    current: dict[tuple[str, str, str, str], DomainRecord] = {}
    for row in rows:
        key = (row.domain_key, row.entity_type, row.source_system, row.source_record_id)
        if key not in current or row.revision > current[key].revision:
            current[key] = row
    counts: dict[str, int] = {}
    programs: set[str] = set()
    for row in current.values():
        counts[row.domain_key] = counts.get(row.domain_key, 0) + 1
        if row.program_code:
            programs.add(row.program_code)
    return {
        "record_count": len(current),
        "program_count": len(programs),
        "domain_counts": counts,
    }
