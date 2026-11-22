from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app.db.migrations import migrate_prototype_schema
from app.db.session import create_app_engine
from app.domain_catalog import entity_domain
from app.models.database import Base
from app.services.domain_validation import validate_domain_record


def test_engine_supports_sqlite_and_rejects_unknown_backends():
    engine = create_app_engine("sqlite:///:memory:")
    try:
        assert engine.dialect.name == "sqlite"
        assert engine.get_execution_options()["schema_translate_map"] == {"mbse": None}
    finally:
        engine.dispose()

    with pytest.raises(ValueError, match="Unsupported database"):
        create_app_engine("mysql+pymysql://user:pass@localhost/example")


def test_additive_migration_backfills_legacy_status_and_is_idempotent():
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE staging_upload (status TEXT NOT NULL)"))
            connection.execute(text("INSERT INTO staging_upload (status) VALUES ('APPROVED'), ('INVALID')"))
            connection.execute(text("CREATE TABLE staging_record (id INTEGER PRIMARY KEY)"))
            connection.execute(text("CREATE TABLE domain_record (id INTEGER PRIMARY KEY)"))

        migrate_prototype_schema(engine)
        migrate_prototype_schema(engine)

        columns = {column["name"] for column in inspect(engine).get_columns("staging_upload")}
        assert {"validation_status", "governance_status", "promotion_status"} <= columns
        with engine.connect() as connection:
            rows = connection.execute(text("SELECT status, validation_status, governance_status FROM staging_upload ORDER BY rowid")).all()
        assert rows == [("APPROVED", "VALIDATED", "APPROVED"), ("INVALID", "INVALID", "PENDING")]
    finally:
        engine.dispose()


def test_domain_validation_checks_contract_and_promoted_references():
    engine = create_app_engine("sqlite:///:memory:")
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            missing_reference = validate_domain_record(
                session,
                "program",
                {"name": "Program", "program_code": "P-1", "organization_code": "ORG-MISSING"},
                "TEST",
                "P-1",
            )
            invalid_contract = validate_domain_record(
                session,
                "organization",
                {"name": "No business code"},
                "TEST",
                "ORG-1",
            )

        assert any("no promoted organization" in error for error in missing_reference)
        assert any("organization_code" in error for error in invalid_contract)
        assert entity_domain("organization") == "organization_program"
        assert entity_domain("unknown") is None
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
