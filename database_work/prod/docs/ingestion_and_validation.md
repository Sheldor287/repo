# Ingestion and validation

This document describes the intended prototype workflow. The end-to-end flow is
not implemented yet; the current upload endpoint and staging models are
experimental.

## Contract source

SQLAlchemy model definitions are the authoritative schema. JSON Schema, CSV
headers, DDL, and ODCS descriptions are derived artifacts. Each derived
contract should identify the model/schema version it represents so an upload
can be validated against the intended contract.

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

Validate each row against the selected contract. Invalid rows are quarantined
with the original input and validation errors. Upload application is atomic: if
the upload cannot be applied as a whole, no partial model changes are committed.
The exact relationship between row quarantine and upload-level failure still
needs to be specified. In particular, decide whether an upload containing any
invalid row is wholly quarantined or whether valid rows may be staged while the
invalid rows are retained separately; the database transaction must not apply
only part of the model update.

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
- `app/api/ingest.py` accepts the current eight-column CSV contract, validates
  the full file, and atomically stages valid uploads. Invalid files receive an
  HTTP validation error; durable quarantine handling is not implemented.
- `app/main.py` serves the upload page at `/` and initializes the registered
  model tables at startup for local development.
- The `data/landing`, `data/quarantine`, and `data/archive` directories are
  reserved locations; a file storage policy has not been selected.
