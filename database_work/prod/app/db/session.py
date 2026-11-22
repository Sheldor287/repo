from __future__ import annotations
import os
from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker


DEFAULT_DATABASE_URL = "sqlite:///./app.db"


def create_app_engine(database_url: str | None = None) -> Engine:
    """Create an engine for SQLite or PostgreSQL.

    MBSE tables declare the ``mbse`` schema. SQLite has no schema support, so
    translate that schema to the default namespace for SQLite connections.
    """
    url = make_url(database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL))
    if url.get_backend_name() not in {"sqlite", "postgresql"}:
        raise ValueError(
            f"Unsupported database {url.get_backend_name()!r}; "
            "configure SQLite or PostgreSQL."
        )

    options: dict[str, object] = {"pool_pre_ping": True}
    if url.get_backend_name() == "sqlite":
        options["connect_args"] = {"check_same_thread": False}

    engine = create_engine(url, **options)
    if url.get_backend_name() == "sqlite":
        engine = engine.execution_options(schema_translate_map={"mbse": None})
    return engine


engine = create_app_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Yield a session and always close it after the request."""
    with SessionLocal() as session:
        yield session
