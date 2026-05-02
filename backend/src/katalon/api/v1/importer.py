from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

from katalon.services import importer_service

router = APIRouter(prefix="/importer", tags=["importer"])

MAX_SIZE = 10 * 1024 * 1024  # 10 MB


class MappingRequest(BaseModel):
    mapping: dict[str, str]
    rows: list[dict[str, str]]


class DryRunRequest(MappingRequest):
    pass


class ImportRequest(BaseModel):
    mapping: dict[str, str]
    rows: list[dict[str, str]]
    record_type: str = "object"


@router.post("/upload")
async def upload_file(file: UploadFile) -> dict:
    content = await file.read(MAX_SIZE + 1)
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="Datei zu groß (max 10 MB)")
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=422, detail="Nur CSV-Dateien werden unterstützt")
    headers, rows = importer_service.parse_csv(content)
    return {"headers": headers, "row_count": len(rows), "preview": rows[:5], "rows": rows}


@router.post("/dry-run")
async def dry_run(body: DryRunRequest) -> dict:
    return importer_service.dry_run(body.rows, body.mapping)


@router.post("/import")
async def run_import(body: ImportRequest) -> dict:
    from katalon.workers.import_tasks import import_records_task
    task = import_records_task.delay(body.record_type, body.rows, body.mapping)
    return {"status": "queued", "task_id": task.id}
