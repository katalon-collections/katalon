from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import select

from katalon.core.dependencies import CurrentUser, DBDep
from katalon.core.models import FieldDefinition
from katalon.services import importer_service

router = APIRouter(prefix="/importer", tags=["importer"])

MAX_SIZE = 50 * 1024 * 1024  # 50 MB

VALID_TYPES = {"object", "entity", "place", "occurrence"}


class MappingRequest(BaseModel):
    mapping: dict[str, str]   # csv_column -> field_name
    rows: list[dict[str, str]]
    record_type: str = "object"


class ImportRequest(MappingRequest):
    pass


@router.post("/upload")
async def upload_file(file: UploadFile, _: CurrentUser) -> dict:
    content = await file.read(MAX_SIZE + 1)
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="Datei zu groß (max 50 MB)")
    filename = (file.filename or "").lower()
    if filename.endswith(".xlsx"):
        headers, rows = importer_service.parse_excel(content)
    elif filename.endswith(".csv") or filename.endswith(".tsv"):
        headers, rows = importer_service.parse_csv(content)
    else:
        raise HTTPException(status_code=422, detail="Nur CSV, TSV und Excel (.xlsx) werden unterstützt")
    return {"headers": headers, "row_count": len(rows), "preview": rows[:5], "rows": rows}


@router.post("/dry-run")
async def dry_run(body: MappingRequest, db: DBDep, _: CurrentUser) -> dict:
    if body.record_type not in VALID_TYPES:
        raise HTTPException(status_code=422, detail=f"Ungültiger Typ: {body.record_type}")
    result = await db.execute(
        select(FieldDefinition).where(
            FieldDefinition.target_type == body.record_type,
            FieldDefinition.is_deleted.is_(False),
        )
    )
    field_defs = {f.name: f for f in result.scalars().all()}
    return importer_service.dry_run(body.rows, body.mapping, field_defs)


@router.post("/import")
async def run_import(body: ImportRequest, _: CurrentUser) -> dict:
    if body.record_type not in VALID_TYPES:
        raise HTTPException(status_code=422, detail=f"Ungültiger Typ: {body.record_type}")
    from katalon.workers.import_tasks import import_records_task
    task = import_records_task.delay(body.record_type, body.rows, body.mapping)
    return {"status": "queued", "task_id": task.id}


@router.get("/task/{task_id}")
async def task_status(task_id: str, _: CurrentUser) -> dict:
    from celery.result import AsyncResult
    from katalon.workers.celery_app import celery_app
    result = AsyncResult(task_id, app=celery_app)
    state = result.state  # PENDING / STARTED / SUCCESS / FAILURE
    if state == "SUCCESS":
        return {"state": state, "result": result.result}
    if state == "FAILURE":
        return {"state": state, "error": str(result.result)}
    return {"state": state}
