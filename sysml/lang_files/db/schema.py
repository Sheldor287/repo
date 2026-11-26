from __future__ import annotations

import re

from sqlalchemy import (
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    event,
)

# Portable SQLAlchemy Core schema: shared by SQLite and PostgreSQL.
# UUIDs and timestamps are represented as strings; JSON payloads as TEXT.
metadata = MetaData()

artifacts = Table(
    "lang_artifact", metadata,
    Column("artifact_id", String(36), primary_key=True),
    Column("source", Text, nullable=False, default="OMG"),
    Column("specification", Text, nullable=False),
    Column("version", Text),
    Column("omg_file_id", Text),
    Column("filename", Text, nullable=False),
    Column("format", Text, nullable=False),
    Column("artifact_role", Text, nullable=False, default="MODEL"),
    Column("description", Text),
    Column("normative_status", Text),
    Column("url", Text, nullable=False),
    Column("sha256", String(64)),
    Column("local_path", Text),
    Column("object_uri", Text),
    Column("model_uri", Text),
    Column("retrieved_at", Text),
    Column("http_status", Integer),
    Column("download_status", Text),
    Column("parse_status", Text, nullable=False, default="REGISTERED"),
    Column("parse_error", Text),
    Column("manifest_json", Text),
    UniqueConstraint("specification", "version", "url", "sha256", name="uq_lang_artifact_spec_version_url_hash"),
)
Index("ix_lang_artifact_spec_version", artifacts.c.specification, artifacts.c.version)
Index("ix_lang_artifact_sha256", artifacts.c.sha256)

runs = Table(
    "lang_ingestion_run", metadata,
    Column("run_id", String(36), primary_key=True),
    Column("started_at", Text, nullable=False),
    Column("completed_at", Text),
    Column("status", Text, nullable=False),
    Column("parser_version", Text, nullable=False),
    Column("database_dialect", Text),
    Column("summary_json", Text),
)

nodes = Table(
    "lang_element", metadata,
    Column("element_id", String(36), primary_key=True),
    Column("artifact_id", String(36), ForeignKey("lang_artifact.artifact_id", ondelete="CASCADE"), nullable=False),
    Column("parent_element_id", String(36), ForeignKey("lang_element.element_id", ondelete="CASCADE")),
    Column("ordinal", Integer, nullable=False),
    Column("xmi_id", Text),
    Column("metaclass", Text),
    Column("xml_tag", Text, nullable=False),
    Column("namespace_uri", Text),
    Column("name", Text),
    Column("xml_path", Text, nullable=False),
    UniqueConstraint("artifact_id", "ordinal", name="uq_lang_element_artifact_ordinal"),
)
Index("ix_lang_element_xmi_id", nodes.c.xmi_id)
Index("ix_lang_element_artifact_xmi_id", nodes.c.artifact_id, nodes.c.xmi_id)
Index("ix_lang_element_name", nodes.c.name)
Index("ix_lang_element_metaclass", nodes.c.metaclass)

properties = Table(
    "lang_element_property", metadata,
    Column("property_id", String(36), primary_key=True),
    Column("element_id", String(36), ForeignKey("lang_element.element_id", ondelete="CASCADE"), nullable=False),
    Column("property_name", Text, nullable=False),
    Column("value_text", Text),
    Column("value_kind", Text, nullable=False),
    Column("ordinal", Integer, nullable=False, default=0),
    Column("xml_path", Text, nullable=False),
    Column("attributes_json", Text),
)
Index("ix_lang_property_element_name", properties.c.element_id, properties.c.property_name)

references = Table(
    "lang_relationship", metadata,
    Column("reference_id", String(36), primary_key=True),
    Column("artifact_id", String(36), ForeignKey("lang_artifact.artifact_id", ondelete="CASCADE"), nullable=False),
    Column("source_element_id", String(36), ForeignKey("lang_element.element_id", ondelete="CASCADE"), nullable=False),
    Column("reference_kind", Text, nullable=False),
    Column("relationship_kind", Text, nullable=False),
    Column("target_raw", Text, nullable=False),
    Column("target_uri", Text),
    Column("target_fragment", Text),
    Column("target_xmi_id", Text),
    Column("target_element_id", String(36), ForeignKey("lang_element.element_id", ondelete="SET NULL")),
    Column("resolution_status", Text, nullable=False, default="UNRESOLVED"),
    Column("xml_path", Text, nullable=False),
)
Index("ix_lang_reference_target", references.c.target_xmi_id)
Index("ix_lang_reference_resolved", references.c.target_element_id)
Index("ix_lang_reference_kind", references.c.relationship_kind)

mappings = Table(
    "lang_element_mapping", metadata,
    Column("mapping_id", String(36), primary_key=True),
    Column("source_element_id", String(36), ForeignKey("lang_element.element_id", ondelete="CASCADE"), nullable=False),
    Column("target_element_id", String(36), ForeignKey("lang_element.element_id", ondelete="CASCADE")),
    Column("evidence_artifact_id", String(36), ForeignKey("lang_artifact.artifact_id", ondelete="CASCADE"), nullable=False),
    Column("evidence_element_id", String(36), ForeignKey("lang_element.element_id", ondelete="SET NULL")),
    Column("mapping_kind", Text, nullable=False),
    Column("mapping_method", Text, nullable=False),
    Column("confidence", Float),
    Column("mapping_status", Text, nullable=False, default="CANDIDATE"),
    Column("evidence_text", Text),
    Column("created_at", Text, nullable=False),
)
Index("ix_lang_mapping_source", mappings.c.source_element_id)
Index("ix_lang_mapping_target", mappings.c.target_element_id)
Index("ix_lang_mapping_evidence", mappings.c.evidence_artifact_id)

mapping_rules = Table(
    "lang_mapping_rule", metadata,
    Column("mapping_rule_id", String(36), primary_key=True),
    Column("artifact_id", String(36), ForeignKey("lang_artifact.artifact_id", ondelete="CASCADE"), nullable=False),
    Column("mapping_element_id", String(36), ForeignKey("lang_element.element_id", ondelete="CASCADE"), nullable=False, unique=True),
    Column("rule_name", Text, nullable=False),
    Column("source_type_uri", Text),
    Column("source_type_fragment", Text),
    Column("target_type_hint", Text),
    Column("extraction_method", Text, nullable=False),
    Column("rule_status", Text, nullable=False, default="RULE_DEFINITION"),
    Column("evidence_json", Text),
)
Index("ix_lang_mapping_rule_name", mapping_rules.c.rule_name)


def make_engine(url: str, schema_name: str = "sysml"):
    """Create a portable engine; PostgreSQL tables are placed in schema_name."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", schema_name):
        raise ValueError("schema_name must be a simple SQL identifier")
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    elif url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    engine = create_engine(url, future=True)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    elif engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.exec_driver_sql(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"')
        engine = engine.execution_options(schema_translate_map={None: schema_name})
    return engine


def create_schema(engine) -> None:
    metadata.create_all(engine)
