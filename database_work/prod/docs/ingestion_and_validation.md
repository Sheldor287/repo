# Ingestion and validation

This document describes the prototype workflow. The general-purpose mock
domain path is implemented; the legacy sample CSV path remains experimental.
See [the mock domain guide](mock_domains.md) for its entity catalog and request
contract.

## Contract source

SQLAlchemy models define the current physical persistence schema.
`app/domain_catalog.py` defines a separate, bounded set of notional API
contracts. They are not the conceptual domain model or the final normalized
database schema. Each inbound batch identifies its contract version, and each
validation run records both the contract and validator version used.

## Upload event

An upload is an auditable event. The eventual upload record should include:

- user and the user's organization;
- upload method;
- targeted schema(s) and table(s);
- UTC upload time;
- source filename and content hash, when applicable;
- contract version and row outcome counts.

The internal upload identifier identifies the event. Row UUIDs identify stored
rows; the logical identity of a model object across append-only revisions is
established from source metadata or user input. A source record identifier may
be retained as provenance when the source system provides one.

## Validation, quarantine, and atomicity

Validate each row against the selected contract. Invalid domain JSON row
payloads are retained in an `INVALID` staged batch with validation errors.
Upload application is atomic: if the upload cannot be applied as a whole, no
partial model changes are committed.

For the domain JSON endpoint, any invalid row makes the whole batch `INVALID`.
All rows and row-level outcomes remain in staging, but no row in that batch may
be promoted. The staging write and an approved batch promotion are each
transactional. The legacy CSV endpoint rejects invalid input before it creates
a staging record.

## MBSE history

MBSE history is append-only. INSERT, UPDATE, and DELETE records are retained,
and the current state is derived from the revision history for each logical
entity. UPDATE and DELETE are especially relevant to object and relationship
definitions and their properties. Every uploaded model and its row-level
changes should be traceable to the upload event.

## Current implementation status

- `app/db/session.py` provides SQLite and PostgreSQL engine selection and a
  request-scoped session dependency.
- `app/models/ingest.py` defines staging upload and staging record tables.
- `StagingUpload.status` remains as a compatibility column for the original CSV
  prototype. New workflows use separate validation, governance, and promotion
  status columns.
- The legacy CSV endpoint accepts its eight-column sample contract and
  atomically stages valid files. Invalid CSV receives an HTTP validation error
  and is not durably quarantined; retained invalid batches are implemented for
  the newer domain JSON endpoint.
- `POST /api/ingest/domain/{entity_type}` accepts versioned JSON contracts from
  `app/domain_catalog.py`. Field-level errors are persisted with invalid batch
  records; structural, type, duplicate-ID, business-key, and selected
  relationship checks run before the batch can be approved.
- Validation, governance, and promotion use separate status fields. Each batch
  also stores an append-only validation run with the contract version,
  validator version, counts, errors, and execution timestamp.
- Approved domain batches are promoted atomically into the generic
  `domain_record` prototype store. Each representation retains the source
  record ID, source system, source batch, explicit authority status, and a new
  revision; prior versions are preserved. Entity payloads remain JSON-backed,
  so this is not yet the target normalized relational domain model.
- `GET /api/domains`, `GET /api/records`, and `GET /api/overview` provide the
  catalog, current/history views, and organization-wide dashboard counts.
- Batch review is available through `GET /api/ingest/uploads` and
  `POST /api/ingest/uploads/{upload_uuid}/governance`. A validated upload can
  receive one approval or rejection, recorded as a separate decision with
  reviewer-supplied identity, reason, and timestamp. Validation status remains
  distinct from governance status and promotion status; subsequent decisions
  are rejected.
- The dashboard and legacy upload page list staged batches and provide batch-level review
  controls. Authentication is not implemented, so the reviewer name is
  submitted as data and is not a verified identity.
- Governance approval triggers promotion for domain JSON batches. The ERP does
  not infer authority from approval or storage: promoted records are marked
  ERP-authoritative, externally authoritative, unassigned, or in conflict based
  on approved `data_authority` records. The legacy CSV contract is not promoted.
- `app/main.py` serves the upload page at `/` and initializes the registered
  model tables at startup for local development.
- The `data/landing`, `data/quarantine`, and `data/archive` directories are
  reserved locations; a file storage policy has not been selected.
