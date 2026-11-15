from sqlalchemy import create_engine, event
from pathlib import Path
import sys
backend = Path.cwd().parents[1]/"backend"
data_dir = Path.cwd().parents[0]/"test_data"
db_path = f"sqlite:///{data_dir}/mbse_sim.db"
sys.path.insert(0, str(backend))
from app.models.database import MBSE
import app.models

engine = create_engine(db_path, echo=True)

# Enable foreign key enforcement
@event.listens_for(engine, "connect")
def enable_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

# Translate PostgreSQL-style schema references
sqlite_engine = engine.execution_options(
    schema_translate_map={"mbse": None}
)

# Create all existing MBSE tables
MBSE.metadata.create_all(sqlite_engine)

# Verify
with sqlite_engine.connect() as conn:
    print("Foreign keys enabled:",
          conn.exec_driver_sql("PRAGMA foreign_keys").scalar())

    tables = conn.exec_driver_sql("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        ORDER BY name
    """).fetchall()

    print("\nSQLite tables:")
    for table in tables:
        print(table[0])

