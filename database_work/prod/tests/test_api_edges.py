from __future__ import annotations

from uuid import uuid4

from app.api.ingest import EXPECTED_COLUMNS, parse_csv
from fastapi import HTTPException
import pytest



def stage_batch(client, entity_type: str, records: list[dict], source_system: str = "TEST-SOURCE"):
    return client.post(
        f"/api/ingest/domain/{entity_type}",
        json={"source_system": source_system, "contract_version": "1.0", "records": records},
    )


def submit_and_approve(client, entity_type: str, source_record_id: str, data: dict):
    staged = stage_batch(client, entity_type, [{"source_record_id": source_record_id, "data": data}])
    assert staged.status_code == 201, staged.text
    batch = staged.json()
    approved = client.post(
        f"/api/ingest/uploads/{batch['upload_uuid']}/governance",
        json={"decision": "APPROVED", "decided_by": "Tester", "reason": "Verified"},
    )
    assert approved.status_code == 200, approved.text
    return batch, approved.json()


def _csv_row(record_uuid: str | None = None, **overrides: str) -> str:
    values = {
        "uuid": record_uuid or str(uuid4()),
        "name": "Example",
        "phone": "555-0100",
        "job": "Planner",
        "vin": "VIN-1",
        "city": "Boston",
        "governance_status": "PENDING",
        "created_at": "2026-01-02T03:04:05",
    }
    values.update(overrides)
    return ",".join(values[column] for column in EXPECTED_COLUMNS)


def test_csv_parser_accepts_utf8_bom_and_strips_values():
    content = ("\ufeff" + ",".join(EXPECTED_COLUMNS) + "\n" + _csv_row(name="  Example  ") + "\n").encode()

    records = parse_csv(content)

    assert len(records) == 1
    assert records[0]["name"] == "Example"


def test_csv_parser_rejects_duplicate_uuids_and_bad_contract():
    record_uuid = str(uuid4())
    header = ",".join(EXPECTED_COLUMNS)
    with pytest.raises(HTTPException, match="duplicates UUID"):
        parse_csv(f"{header}\n{_csv_row(record_uuid)}\n{_csv_row(record_uuid)}".encode())
    with pytest.raises(HTTPException, match="CSV columns"):
        parse_csv(b"uuid,name\n1,Example")


def test_csv_parser_rejects_invalid_timestamps_and_empty_files():
    header = ",".join(EXPECTED_COLUMNS)
    with pytest.raises(HTTPException, match="invalid created_at"):
        parse_csv(f"{header}\n{_csv_row(created_at='yesterday')}".encode())
    with pytest.raises(HTTPException, match="no data rows"):
        parse_csv(f"{header}\n".encode())


def test_domain_ingestion_rejects_unknown_entity_and_invalid_batch_shape(client):
    unknown = stage_batch(client, "not_a_real_entity", [{"source_record_id": "X", "data": {}}])
    empty = client.post("/api/ingest/domain/organization", json={"source_system": "TEST", "records": []})
    version = client.post("/api/ingest/domain/organization", json={"source_system": "TEST", "contract_version": "99", "records": [{"source_record_id": "X", "data": {}}]})

    assert unknown.status_code == 404
    assert empty.status_code == 400
    assert version.status_code == 400
    assert client.get("/api/ingest/uploads").json() == []


def test_governance_input_and_missing_upload_errors(client):
    malformed = client.post("/api/ingest/uploads/not-a-uuid/governance", json={})
    missing = client.post(f"/api/ingest/uploads/{uuid4()}/governance", json={"decision": "APPROVED", "decided_by": "Reviewer", "reason": "Reviewed"})
    invalid = client.post(f"/api/ingest/uploads/{uuid4()}/governance", json={"decision": "PENDING", "decided_by": "Reviewer", "reason": "Reviewed"})

    assert malformed.status_code == 422
    assert missing.status_code == 404
    assert invalid.status_code == 400


def test_record_filters_and_overview_reflect_current_revisions(client):
    submit_and_approve(client, "organization", "ORG-A", {"name": "A", "organization_code": "ORG-A"})
    submit_and_approve(client, "organization", "ORG-A", {"name": "A updated", "organization_code": "ORG-A"})
    submit_and_approve(client, "organization", "ORG-B", {"name": "B", "organization_code": "ORG-B"})

    current = client.get("/api/records?domain=organization_program&entity_type=organization&limit=1")
    history = client.get("/api/records?entity_type=organization&history=true")
    overview = client.get("/api/overview").json()

    assert current.status_code == 200 and len(current.json()) == 1
    assert len(history.json()) == 3
    assert overview["record_count"] == 2
    assert overview["domain_counts"]["organization_program"] == 2
