from __future__ import annotations

from collections.abc import Iterator
from functools import partial

from anyio.from_thread import start_blocking_portal
from httpx import ASGITransport, AsyncClient, Response
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.db.session as db_session
import app.main as app_main


class LocalASGITestClient:
    """Small synchronous wrapper over httpx's ASGI transport.

    This avoids Starlette's deprecated httpx-backed TestClient while keeping
    the test cases synchronous and running the app lifespan explicitly.
    """

    def __init__(self, app) -> None:
        self.app = app

    def __enter__(self):
        self._portal_manager = start_blocking_portal()
        self._portal = self._portal_manager.__enter__()
        self._portal.call(self._start)
        return self

    async def _start(self) -> None:
        self._lifespan = self.app.router.lifespan_context(self.app)
        await self._lifespan.__aenter__()
        self._client = AsyncClient(
            transport=ASGITransport(app=self.app),
            base_url="http://testserver",
        )

    async def _stop(self, exc_type, exc, traceback) -> None:
        await self._client.aclose()
        await self._lifespan.__aexit__(exc_type, exc, traceback)

    def __exit__(self, exc_type, exc, traceback) -> None:
        self._portal.call(self._stop, exc_type, exc, traceback)
        self._portal_manager.__exit__(exc_type, exc, traceback)

    def get(self, url: str, **kwargs) -> Response:
        return self._portal.call(partial(self._client.get, url, **kwargs))

    def post(self, url: str, **kwargs) -> Response:
        return self._portal.call(partial(self._client.post, url, **kwargs))


@pytest.fixture
def client(tmp_path, monkeypatch) -> Iterator[LocalASGITestClient]:
    """Run each API test against a disposable SQLite database."""
    database_path = tmp_path / "erp-tests.sqlite"
    raw_engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    test_engine = raw_engine.execution_options(schema_translate_map={"mbse": None})
    test_sessions = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(app_main, "engine", test_engine)
    monkeypatch.setattr(db_session, "SessionLocal", test_sessions)

    try:
        with LocalASGITestClient(app_main.app) as test_client:
            yield test_client
    finally:
        raw_engine.dispose()
