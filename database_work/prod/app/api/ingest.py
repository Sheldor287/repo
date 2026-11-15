from __future__ import annotations

import hashlib
import io
from datetime import datetime, timezone
from uuid import UUID

from isort import file
import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session


from app.models.database import get_db
from app.models.ingest import StagingRecord, StagingUpload
from models.enum_objects import ValidationStatus as Status

router = APIRouter(prefix="/api/ingest", tags=["ingest"],)
@router.post("/upload")
async def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db),):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="CSV file is required")
    # Read the file content into memory
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="File content is required")
    # File validation
    file_hash = hashlib.sha256(content).hexdigest()
    # Parse
    try: 
        df = pd.read_csv(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV file: {e}")

class IngestService:
    def __init__(self, prefix="api/ingest", tags=["ingest"], db: Session = Depends(get_db)):
        self.prefix = prefix
        self.tags = tags
        self.db = db

    def set_file(self, file: UploadFile):
        self.file = file

    def get_router(self):
        return APIRouter(prefix=self.prefix, tags=self.tags)

    def get_file(self):
        router = self.get_router()
        @router.post("/upload")
        async def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db),):
            self.set_file(file)
            self._name_validation(file)
            content = await file.read()
            self._content_validation(content)
            self.file_hash = hashlib.sha256(content).hexdigest()
            try:
                df = pd.read_csv(io.BytesIO(content))
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid CSV file: {e}")
            self._schema_validation(df)
            self._uuid_validation(df)
            # df has been promoted to an attribute after passing validation
            record = self.create_staging_record()
            return record
        return router
        
    def create_staging_record(self):
        upload = StagingUpload(
            filename=self.file.filename,
            uploaded_at=datetime.now(timezone.utc),
            status=Status.VALIDATED,
            record_count=len(self.df),
            file_hash=self.file_hash,
            )
        self.db.add(upload)
        self.db.flush()

        for index, row in self.df.iterrows():
            record = StagingRecord(
                upload_uuid = upload.uuid,
                record_uuid = UUID(str(row["uuid"])),
                row_number = index+2,
                validation_status=Status.PENDING,
                raw_data = row.to_dict(),
            )
            self.db.add(record)
        self.db.commit()
        return {
        "upload_uuid": str(upload.uuid),
        "filename": upload.filename,
        "record_count": upload.record_count,
        "status": upload.status,
        "file_hash": upload.file_hash,
    }

    def _name_validation(self, file: UploadFile):
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename is required")
        if not file.filename.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail="CSV file is required")

    def _content_validation(self, content: bytes):
        if not content:
            raise HTTPException(status_code=400, detail="File content is required")

    def _schema_validation(self, df: pd.DataFrame):
        if not all(column in df.columns for column in self.expected_columns):
            raise HTTPException(status_code=400, detail="Invalid CSV schema")
        self.df = df[self.expected_columns] 

    def _uuid_validation(self, df: pd.DataFrame):
        invalid_uuid_rows = []
        for index, value in df["uuid"].items():
            try:
                UUID(str(value))
            except (ValueError, TypeError, AttributeError):
                invalid_uuid_rows.append(index+2)
        if invalid_uuid_rows:
            raise HTTPException(status_code=400, detail="Invalid UUID values")

        duplicate_uuids = (df.loc[df["uuid"].duplicated(keep=False), "uuid"] .astype(str) .unique() .tolist())
        if duplicate_uuids:
            raise HTTPException(status_code=400, detail="Duplicate UUID values")


class TestIngestion(IngestService):
    def __init__(self):
        super().__init__()
        self.expected_columns = [
            'uuid',
            'name',
            'phone',
            'job',
            'vin',
            'city',
            'governance_status',
            'created_at'
            ]


