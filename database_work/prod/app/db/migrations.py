"""Small idempotent additive migrations for the local prototype database.

The project has not adopted Alembic yet. This bootstrap keeps older local
SQLite/PostgreSQL prototype databases compatible with newly added nullable
staging metadata while remaining safe to run on every startup.
"""
from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


ADDITIVE_COLUMNS = {
    "staging_upload": {
        "domain_key": "TEXT",
        "entity_type": "TEXT",
        "source_system": "TEXT",
        "contract_version": "TEXT",
        "validation_status": "TEXT NOT NULL DEFAULT 'PENDING'",
        "governance_status": "TEXT NOT NULL DEFAULT 'PENDING'",
        "promotion_status": "TEXT NOT NULL DEFAULT 'NOT_PROMOTED'",
    },
    "staging_record": {
        "source_record_id": "TEXT",
        "validation_errors": "JSON",
    },
    "domain_record": {
        "authority_status": "TEXT NOT NULL DEFAULT 'UNASSIGNED'",
        "authoritative_system": "TEXT",
    },
}


def migrate_prototype_schema(engine: Engine) -> None:
    """Add missing nullable columns to an existing prototype schema."""
    with engine.begin() as connection:
        inspector = inspect(connection)
        for table_name, columns in ADDITIVE_COLUMNS.items():
            existing = {column["name"] for column in inspector.get_columns(table_name)}
            for column_name, sql_type in columns.items():
                if column_name not in existing:
                    nullability = "" if "NOT NULL" in sql_type else " NULL"
                    connection.execute(
                        text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {sql_type}{nullability}")
                    )
                    existing.add(column_name)
        connection.execute(
            text(
                "UPDATE staging_upload SET validation_status = status "
                "WHERE validation_status = 'PENDING' "
                "AND status IN ('DRAFT', 'UPLOADED', 'PARSED', 'VALIDATED', 'INVALID')"
            )
        )
        connection.execute(
            text(
                "UPDATE staging_upload SET validation_status = 'VALIDATED', governance_status = status "
                "WHERE validation_status = 'PENDING' AND status IN ('APPROVED', 'REJECTED')"
            )
        )
