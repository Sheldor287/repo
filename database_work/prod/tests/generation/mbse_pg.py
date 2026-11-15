
# create_mbse_test.py

import os
from pathlib import Path
import sys
from sqlalchemy import create_engine, inspect
from sqlalchemy.schema import CreateSchema

backend = Path.cwd().parents[1]/"backend"
sys.path.insert(0, str(backend))
from app.models.database import MBSE
import app.models  # Ensure all model classes are registered


DATABASE_URL = os.environ["PG_CONN"]
TARGET_SCHEMA = "mbse_test"

engine = create_engine(DATABASE_URL, echo=True, pool_pre_ping=True,)

# Verify that this is a PostgreSQL connection.
if engine.dialect.name != "postgresql":
    raise RuntimeError(f"Expected PostgreSQL, got {engine.dialect.name}")

# Redirect the existing MBSE schema to the test schema.
test_engine = engine.execution_options(
    schema_translate_map={"mbse": TARGET_SCHEMA}
)
try:
    with engine.begin() as conn:
        # Create the destination schema if necessary.
        conn.execute(CreateSchema(TARGET_SCHEMA, if_not_exists=True))

        # Create all registered MBSE tables in mbse_test.
        MBSE.metadata.create_all(
            bind=conn.execution_options(
                schema_translate_map={"mbse": TARGET_SCHEMA}
            )
        )
    # Verify the resulting schema.
    inspector = inspect(engine)
    tables = inspector.get_table_names(schema=TARGET_SCHEMA)
    print(f"\nCreated schema: {TARGET_SCHEMA}")
    print(f"Tables created: {len(tables)}")
    for table in sorted(tables):
        print(f"  - {TARGET_SCHEMA}.{table}")
finally:
    engine.dispose()
