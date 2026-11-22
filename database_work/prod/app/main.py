from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.api.domain import router as domain_router
from app.api.ingest import router as ingest_router
from app.db.migrations import migrate_prototype_schema
from app.db.session import engine
from app.models.database import Base, MBSE
from app.models.ingest import StagingRecord, StagingUpload  # noqa: F401
import app.models  # noqa: F401  # register all MBSE models with metadata


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Create prototype tables and apply the small additive DB bootstrap."""
    Base.metadata.create_all(engine)
    migrate_prototype_schema(engine)
    MBSE.metadata.create_all(engine)
    yield


app = FastAPI(title="Database Work Prototype", lifespan=lifespan)
app.include_router(ingest_router)
app.include_router(domain_router)


@app.get("/", include_in_schema=False)
async def dashboard_page() -> FileResponse:
    page = Path(__file__).parent / "user_interfaces" / "dashboard.html"
    return FileResponse(page, media_type="text/html")


@app.get("/ingest", include_in_schema=False)
async def legacy_upload_page() -> FileResponse:
    page = Path(__file__).parent / "user_interfaces" / "upload.html"
    return FileResponse(page, media_type="text/html")
