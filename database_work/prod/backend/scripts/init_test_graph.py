from __future__ import annotations
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
import argparse, csv, os, sys
from pathlib import Path
from uuid import UUID

# Project imports
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
from app.database import Base
from database.prod.backend.app.models.mbse.depr.element import Element
from database.prod.backend.app.models.mbse.depr.relationship import Relationship
from database.prod.backend.app.models.mbse.depr.semantic import Semantic

# Configuration
PROJECT_DIR = BACKEND_DIR.parent

DEFAULT_DATA_DIR = PROJECT_DIR / "tests" / "test_data"

EXPECTED_TABLES = {"test.elements", "test.relationships", "test.semantic_relationships",}

CSV_COLUMNS = {
    "relationships": ["relationship_uuid", "name", "definition",],
    "elements": ["element_uuid", "name", "definition",],
    "semantics": ["semantic_uuid", "source_element_uuid", "relationship_uuid", "target_element_uuid",],
}

# CSV loading
def read_csv(filepath: Path, expected_columns: list[str],) -> list[dict]:
    if not filepath.exists():
        raise FileNotFoundError(f"Required CSV file not found: {filepath}")
    with filepath.open("r", newline="", encoding="utf-8-sig",) as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise ValueError(f"{filepath.name} is empty.")
        actual = set(reader.fieldnames)
        expected = set(expected_columns)
        if actual != expected:
            raise ValueError(
                f"Invalid columns in {filepath.name}.\nMissing: {expected - actual}\nUnexpected: {actual - expected}"
                )
        rows = []
        for line_number, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(
                    f"Unexpected extra columns in {filepath.name}, line {line_number}."
                )
            if any(value is None for value in row.values()):
                raise ValueError(
                    f"Missing field in {filepath.name}, line {line_number}."
                )
            rows.append(row)
    return rows

def load_csv_data(data_dir: Path) -> dict[str, list[dict]]:
    return {
        "relationships": read_csv(data_dir / "relationships.csv", CSV_COLUMNS["relationships"],),
        "elements": read_csv(data_dir / "elements.csv", CSV_COLUMNS["elements"],),
        "semantics": read_csv(data_dir / "semantic_relationships.csv", CSV_COLUMNS["semantics"],),
    }

# Data validation
def validate_uuid(value: str, field_name: str, row_number: int,) -> None:
    try:
        UUID(value)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError(f"Invalid UUID in {field_name}, row {row_number}: {value}") from exc

def validate_unique(rows: list[dict], field: str, dataset_name: str,) -> None:
    values = [row[field] for row in rows]
    if len(values) != len(set(values)):
        raise ValueError(f"Duplicate {field} values in {dataset_name}.")

def validate_data(data: dict[str, list[dict]]) -> None:
    relationships = data["relationships"]
    elements = data["elements"]
    semantics = data["semantics"]
    # Required fields
    for dataset_name, rows in data.items():
        for row_number, row in enumerate(rows, start=2):
            for field, value in row.items():
                if not value.strip():
                    raise ValueError(f"Empty value in {dataset_name}, field '{field}', row {row_number}.")
    # UUID validation
    uuid_fields = {
        "relationships": ["relationship_uuid"],
        "elements": ["element_uuid"],
        "semantics": ["semantic_uuid", "source_element_uuid", "relationship_uuid", "target_element_uuid",],
    }
    for dataset_name, fields in uuid_fields.items():
        for row_number, row in enumerate(data[dataset_name], start=2,):
            for field in fields:
                validate_uuid(row[field], field, row_number,)
    # Primary-key uniqueness
    validate_unique(relationships, "relationship_uuid", "relationships",)
    validate_unique(elements, "element_uuid", "elements",)
    validate_unique(semantics, "semantic_uuid", "semantics",)
    # Relationship triple uniqueness
    triples = [(row["source_element_uuid"], row["relationship_uuid"], row["target_element_uuid"],) for row in semantics]
    if len(triples) != len(set(triples)):
        raise ValueError("Duplicate semantic triples found.")
    # Referential integrity
    element_ids = {row["element_uuid"] for row in elements}
    relationship_ids = {row["relationship_uuid"] for row in relationships}
    for row_number, semantic in enumerate(semantics, start=2):
        if semantic["source_element_uuid"] not in element_ids:
            raise ValueError(f"Unknown source element in semantic row {row_number}.")
        if semantic["target_element_uuid"] not in element_ids:
            raise ValueError(f"Unknown target element in semantic row {row_number}.")
        if semantic["relationship_uuid"] not in relationship_ids:
            raise ValueError(f"Unknown relationship in semantic row {row_number}.")

# ORM conversion
def build_orm_objects(data: dict[str, list[dict]]) -> dict:
    relationship_objects = [Relationship(**row) for row in data["relationships"]]
    element_objects = [Element(**row) for row in data["elements"]]
    semantic_objects = [Semantic(**row) for row in data["semantics"]]
    return {"relationships": relationship_objects, "elements": element_objects, "semantics": semantic_objects,}

# Database operations
def check_metadata() -> None:
    missing = EXPECTED_TABLES - set(Base.metadata.tables)
    if missing:
        raise RuntimeError(
            "SQLAlchemy metadata is missing expected tables: " f"{missing}. Check that all MBSE models are imported."
            )

def initialize_database(database_url: str, objects: dict, upsert: bool = False, create_tables: bool = False,) -> None:
    engine = create_engine(database_url, pool_pre_ping=True,)
    try:
        # Initialize the test schema.
        with engine.begin() as connection:
            connection.execute(text("CREATE SCHEMA IF NOT EXISTS test")) 
        # Create tables if requested.
        if create_tables:
            Base.metadata.create_all(engine)
        # All inserts happen within one transaction.
        with Session(engine) as session:
            with session.begin():
                load_order = ["relationships", "elements", "semantics",]
                for dataset_name in load_order:
                    rows = objects[dataset_name]
                    if upsert:
                        #merge() inserts new primary keys and updates existing records with matching primary keys.
                        for obj in rows:
                            session.merge(obj)
                    else:
                        session.add_all(rows)
                    print(f"Staged {len(rows)} {dataset_name} records.")
        print("\nDatabase transaction committed.")
    finally:
        engine.dispose()

def main():
    parser = argparse.ArgumentParser(description="Load generated MBSE graph CSVs into PostgreSQL.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory containing the three generated CSV files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate CSV data without connecting to the database.",
    )
    parser.add_argument(
        "--upsert",
        action="store_true",
        help="Insert new records or update records with matching UUIDs.",
    )
    parser.add_argument(
        "--create-tables",
        action="store_true",
        help="Create missing tables using SQLAlchemy metadata.",
    )
    args = parser.parse_args()
    print(f"Reading CSV files from: {args.data_dir}")
    data = load_csv_data(args.data_dir)
    print("\nValidating data...")
    validate_data(data)
    print("Validation successful.")
    for name, rows in data.items():
        print(f"{name}: {len(rows)} records")
    if args.dry_run:
        print("\nDry run complete. No database changes made.")
        return
    database_url = os.getenv("PG_CONN")
    if not database_url:
        raise RuntimeError("PG_CONN environment variable is not set.")
    check_metadata()
    objects = build_orm_objects(data)
    initialize_database(
        database_url=database_url,
        objects=objects,
        upsert=args.upsert,
        create_tables=args.create_tables,
    )

if __name__ == "__main__":
    main()
