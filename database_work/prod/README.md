# Database Work Prototype

This repository is an early prototype for a multi-domain data system covering
MBSE, logistics, contracts, finance, and programmatics. MBSE is currently the
most developed domain. The repository contains model definitions, ingestion
experiments, schema artifacts, and test data; it is not yet a complete,
deployable application.

## Current layout

```text
prod/
├── app/
│   ├── api/                 # FastAPI route modules
│   ├── db/                  # SQLAlchemy engine and request-scoped sessions
│   ├── main.py              # FastAPI app, page route, and prototype table setup
│   ├── models/
│   │   ├── mbse/            # MBSE SQLAlchemy model definitions
│   │   ├── database.py      # Declarative bases and shared columns
│   │   ├── enum_objects.py  # Shared enums
│   │   └── ingest.py        # Staging upload and record models
│   ├── services/            # Validation and planned service modules
│   └── user_interfaces/    # HTML interface prototypes
├── data/                    # Reserved for data landing/archive/quarantine
├── development_folder/
│   ├── files/               # Derived MBSE schema artifact
│   └── notebooks/           # Exploration notebooks
├── docs/                    # Design and workflow documentation
├── scripts/                 # Development data/setup scripts
├── tests/
│   ├── generation/          # Schema/data generation experiments
│   ├── queries/             # SQL inspection queries
│   └── test_data/           # Example inputs and local SQLite database
├── DockerFile               # Minimal container stub
├── docker-compose.yml       # Empty placeholder
└── folder_structure.json    # Machine-readable high-level layout
```

## Database runtime

`app/db/session.py` creates a SQLAlchemy engine from `DATABASE_URL`. If unset,
it uses `sqlite:///./app.db` for local development. PostgreSQL can be selected
with a URL such as `postgresql+psycopg://user:password@localhost:5432/dbname`;
the matching database driver must be installed. SQLite connections translate
the MBSE schema name into SQLite's default namespace.

The SQLAlchemy model definitions are intended to be authoritative. JSON, CSV,
and other schema descriptions are derived artifacts. PostgreSQL and SQLite are
the initial engine targets. Migration tooling and deployment configuration are
not yet established.

## Run the local upload prototype

Ensure FastAPI, Uvicorn, SQLAlchemy, `python-multipart`, and the selected
database driver are installed. From the repository root, run:

```powershell
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/` to use the upload page. By default the app creates
`app.db` in the current working directory and initializes the registered model
tables at startup. Set `DATABASE_URL` before starting Uvicorn to use PostgreSQL.
The upload endpoint is `POST /api/ingest/upload`.
Use `tests/test_data/ingestion_sample.csv` for the supplied one-row example.

The current CSV test contract requires these columns in this order:

```text
uuid,name,phone,job,vin,city,governance_status,created_at
```

## Intended ingestion behavior

Uploads are events and should be atomic: a failed upload must not leave a
partially applied model. Rows that fail validation are to be quarantined with
their validation errors. The upload record is intended to capture uploader,
organization, upload method, target schema/table, UTC time, and outcome. The
details of the upload contract and the end-to-end workflow are still under
development; see [the ingestion notes](docs/ingestion_and_validation.md).

MBSE history is intended to be append-only. A row UUID identifies a stored row;
the logical identity of an object across revisions must be established from
source metadata or user input. Current state is derived from INSERT, UPDATE,
and DELETE history.

## Prototype limitations

- A local FastAPI entry point now serves the upload page and mounts the CSV
  staging route; other API and service modules are empty or experimental.
- Authentication and authorization are not implemented. The initial role
  categories are DBA (read/write), DS (read all), and User (scoped read); the
  scope rules remain to be defined.
- Alembic migrations, deployment configuration, and a production storage
  strategy are not configured.
- `folder_structure.json` is a high-level map; this README is the human-facing
  description of the current layout.
