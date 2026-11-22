from __future__ import annotations


def test_dashboard_exposes_domain_submission_review_and_display_controls(client):
    response = client.get("/")

    assert response.status_code == 200
    html = response.text
    for marker in (
        "id=\"entity-type\"",
        "id=\"batch-json\"",
        "id=\"stage-button\"",
        "id=\"queue\"",
        "id=\"records\"",
        "/api/domains",
        "/api/ingest/domain/",
        "/api/ingest/uploads/",
        "/api/records",
        "/api/overview",
    ):
        assert marker in html


def test_legacy_ingestion_page_exposes_csv_upload_and_governance_review(client):
    response = client.get("/ingest")

    assert response.status_code == 200
    html = response.text
    assert "id=\"csv-file\"" in html
    assert "accept=\".csv\"" in html
    assert "Upload to Staging" in html
    assert "/api/ingest/upload" in html
    assert "/api/ingest/uploads" in html
