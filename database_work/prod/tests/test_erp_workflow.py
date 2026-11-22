from __future__ import annotations

from typing import Any


def stage_batch(client, entity_type: str, records: list[dict[str, Any]], source_system: str = "TEST-SOURCE"):
    return client.post(
        f"/api/ingest/domain/{entity_type}",
        json={
            "source_system": source_system,
            "contract_version": "1.0",
            "records": records,
        },
    )


def submit_and_approve(
    client,
    entity_type: str,
    source_record_id: str,
    data: dict[str, Any],
    source_system: str = "TEST-SOURCE",
):
    staged = stage_batch(
        client,
        entity_type,
        [{"source_record_id": source_record_id, "data": data}],
        source_system,
    )
    assert staged.status_code == 201, staged.text
    batch = staged.json()
    assert batch["validation_status"] == "VALIDATED"
    approved = client.post(
        f"/api/ingest/uploads/{batch['upload_uuid']}/governance",
        json={"decision": "APPROVED", "decided_by": "Test Reviewer", "reason": "Test approval"},
    )
    assert approved.status_code == 200, approved.text
    return batch, approved.json()


def test_catalog_lists_versioned_bounded_contracts(client):
    response = client.get("/api/domains")

    assert response.status_code == 200
    catalog = response.json()
    assert any(
        entity["key"] == "program" and entity["contract_version"] == "1.0"
        for domain in catalog
        for entity in domain["entities"]
    )
    assert any(
        entity["key"] == "domain_relationship"
        for domain in catalog
        for entity in domain["entities"]
    )


def test_invalid_batch_is_retained_with_separate_statuses_and_validation_run(client):
    response = stage_batch(
        client,
        "organization",
        [
            {"source_record_id": "ORG-1", "data": {"organization_code": "ORG-1"}},
            {"source_record_id": "ORG-2", "data": {"name": "No code"}},
        ],
    )

    assert response.status_code == 201, response.text
    batch = response.json()
    assert batch["validation_status"] == "INVALID"
    assert batch["governance_status"] == "PENDING"
    assert batch["promotion_status"] == "NOT_PROMOTED"
    assert len(batch["validation_errors"]) == 2

    uploads = client.get("/api/ingest/uploads").json()
    stored = next(item for item in uploads if item["upload_uuid"] == batch["upload_uuid"])
    assert stored["validation_runs"][0]["result_status"] == "INVALID"
    assert stored["validation_runs"][0]["valid_count"] == 0
    assert stored["validation_runs"][0]["invalid_count"] == 2
    assert stored["validation_runs"][0]["validator_version"] == "catalog-1.0"

    decision = client.post(
        f"/api/ingest/uploads/{batch['upload_uuid']}/governance",
        json={"decision": "APPROVED", "decided_by": "Reviewer", "reason": "Must not promote"},
    )
    assert decision.status_code == 409
    assert client.get("/api/records").json() == []


def test_program_requires_promoted_organization_reference(client):
    orphan_program = stage_batch(
        client,
        "program",
        [
            {
                "source_record_id": "PRG-1",
                "data": {
                    "name": "Program One",
                    "program_code": "PRG-1",
                    "organization_code": "ORG-MISSING",
                    "status": "active",
                },
            }
        ],
    )
    assert orphan_program.status_code == 201
    assert orphan_program.json()["validation_status"] == "INVALID"
    assert any("no promoted organization" in error for error in orphan_program.json()["validation_errors"][0]["errors"])

    submit_and_approve(
        client,
        "organization",
        "ORG-1",
        {"name": "Example Org", "organization_code": "ORG-1", "status": "active"},
    )
    program, approved = submit_and_approve(
        client,
        "program",
        "PRG-1",
        {
            "name": "Program One",
            "program_code": "PRG-1",
            "organization_code": "ORG-1",
            "status": "active",
        },
    )

    assert approved["governance_status"] == "APPROVED"
    assert approved["promotion_status"] == "PROMOTED"
    assert approved["validation_status"] == "VALIDATED"
    assert program["promotion_status"] == "NOT_PROMOTED"


def test_approval_promotes_versions_and_preserves_history(client):
    first, result = submit_and_approve(
        client,
        "organization",
        "ORG-1",
        {"name": "Original name", "organization_code": "ORG-1", "status": "active"},
    )
    assert result["promotion_status"] == "PROMOTED"
    assert result["governance_status"] == "APPROVED"

    second, _ = submit_and_approve(
        client,
        "organization",
        "ORG-1",
        {"name": "Updated name", "organization_code": "ORG-1", "status": "active"},
    )
    assert first["upload_uuid"] != second["upload_uuid"]

    current = client.get("/api/records?entity_type=organization").json()
    history = client.get("/api/records?entity_type=organization&history=true").json()
    assert len(current) == 1
    assert current[0]["revision"] == 2
    assert current[0]["data"]["name"] == "Updated name"
    assert sorted(item["revision"] for item in history) == [1, 2]


def test_authority_requires_an_explicit_approved_mapping(client):
    submit_and_approve(
        client,
        "data_authority",
        "AUTH-ORG",
        {
            "data_domain": "organization",
            "authoritative_system": "ERP",
            "governance_authority": "Data Governance Board",
            "effective_date": "2000-01-01",
        },
        "GOVERNANCE",
    )
    _, approval = submit_and_approve(
        client,
        "organization",
        "ORG-1",
        {"name": "Example Org", "organization_code": "ORG-1", "status": "active"},
    )

    record = client.get("/api/records?entity_type=organization").json()[0]
    assert approval["promotion_status"] == "PROMOTED"
    assert record["authority_status"] == "ERP_AUTHORITATIVE"
    assert record["authoritative_system"] == "ERP"


def test_rejection_is_audited_without_promotion_and_cannot_be_reversed(client):
    staged = stage_batch(
        client,
        "organization",
        [{"source_record_id": "ORG-1", "data": {"name": "Example Org", "organization_code": "ORG-1"}}],
    ).json()
    path = f"/api/ingest/uploads/{staged['upload_uuid']}/governance"
    rejected = client.post(
        path,
        json={"decision": "REJECTED", "decided_by": "Reviewer", "reason": "Source evidence missing"},
    )

    assert rejected.status_code == 200
    assert rejected.json()["validation_status"] == "VALIDATED"
    assert rejected.json()["governance_status"] == "REJECTED"
    assert rejected.json()["promotion_status"] == "NOT_PROMOTED"
    assert client.get("/api/records").json() == []

    second_decision = client.post(
        path,
        json={"decision": "APPROVED", "decided_by": "Reviewer", "reason": "Changed mind"},
    )
    assert second_decision.status_code == 409
    upload = next(
        item for item in client.get("/api/ingest/uploads").json()
        if item["upload_uuid"] == staged["upload_uuid"]
    )
    assert len(upload["decisions"]) == 1
    assert upload["decisions"][0]["decision"] == "REJECTED"


def test_dashboard_is_served_from_root(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "ERP Common Operating Picture" in response.text
