# Tests

## ERP prototype tests

Run the API, database, service, UI, and end-to-end workflow tests from the repository root:

```powershell
python -m pytest -q tests/test_erp_workflow.py tests/test_api_edges.py tests/test_db_services.py tests/test_ui.py
```

The API tests use a temporary SQLite database per test and do not use or modify
`app.db`. Coverage includes CSV parsing and contract errors, API request and
governance edge cases, record filters and overview counts, engine configuration,
legacy schema migration/backfill and idempotence, domain contract/reference
validation, UI route and control wiring, and the end-to-end staging, validation,
governance, authority, promotion, and revision-history workflows. The lightweight
ASGI transport fixture avoids Starlette's deprecated `httpx`-backed `TestClient`.

The scripts under `tests/generation/` are exploratory schema/data-generation
work and are not part of this pytest command.

