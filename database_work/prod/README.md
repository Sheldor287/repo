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
│   │   └── ingest.py        # Staging, decisions, and promoted domain versions
│   ├── domain_catalog.py    # Notional domain contracts and validation rules
│   ├── services/            # Domain validation, governance, and promotion logic
│   └── user_interfaces/    # ERP dashboard and legacy upload prototype
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

SQLAlchemy models define the current persistent schema. `app/domain_catalog.py`
defines a separate, bounded set of notional API contracts; it is not the final
logical or relational domain model. PostgreSQL and SQLite are the initial
engine targets. Alembic migrations and deployment configuration are not yet
established.

## Run the local ERP prototype

Ensure FastAPI, Uvicorn, SQLAlchemy, `python-multipart`, and the selected
database driver are installed. From the repository root, run:

```powershell
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/` to use the stakeholder dashboard. By default the app creates
`app.db` in the current working directory and initializes the registered model
tables at startup. Set `DATABASE_URL` before starting Uvicorn to use PostgreSQL.
Domain batch ingestion is `POST /api/ingest/domain/{entity_type}`. The legacy
CSV upload endpoint remains at `POST /api/ingest/upload`, with its page at
`/ingest`.

The current CSV test contract requires these columns in this order:

```text
uuid,name,phone,job,vin,city,governance_status,created_at
```

## Intended ingestion behavior

Domain JSON batches are staged, validated, governed at batch level, and
promoted atomically into versioned mock domain records. Invalid rows remain in
an `INVALID` batch with field-level errors. The legacy CSV endpoint retains its
earlier prototype behavior. See [the ingestion notes](docs/ingestion_and_validation.md)
and [mock domain guide](docs/mock_domains.md).

The mock domain catalog and JSON request shape are documented in
[the mock domain guide](docs/mock_domains.md). These contracts are starter
schemas for vertical-slice development, not an approved enterprise data model.

MBSE history is intended to be append-only. A row UUID identifies a stored row;
the logical identity of an object across revisions must be established from
source metadata or user input. Current state is derived from INSERT, UPDATE,
and DELETE history.

## Prototype limitations

- The dashboard supports catalog-driven JSON batch ingestion, field and
  selected reference validation, batch governance review, versioned promotion,
  and explicit authority labels. The normalized relational domain model and
  complete relationship rules remain open.
- Authentication and authorization are not implemented. The initial role
  categories are DBA (read/write), DS (read all), and User (scoped read); the
  scope rules remain to be defined.
- Alembic migrations, deployment configuration, and a production storage
  strategy are not configured. Startup applies only a small idempotent
  additive schema update for the prototype's existing SQLite/PostgreSQL tables.
- `folder_structure.json` is a high-level map; this README is the human-facing
  description of the current layout.
