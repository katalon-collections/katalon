from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import select

from katalon.core.dependencies import CurrentUser, DBDep, require_role
from katalon.core.models import FieldDefinition
from katalon.services import importer_service
from katalon.core.schemas import FieldDefinitionCreate, FieldDefinitionRead

router = APIRouter(prefix="/importer", tags=["importer"])

MAX_SIZE = 10 * 1024 * 1024  # 10 MB (matches frontend limit)

VALID_TYPES = {"object", "entity", "place", "occurrence"}


class MappingRequest(BaseModel):
    mapping: dict[str, str]   # csv_column -> field_name
    rows: list[dict[str, str]]
    record_type: str = "object"


class ImportRequest(MappingRequest):
    idno_strategy: str = "auto"   # "auto" | "column" | "skip"
    upsert_strategy: str = "skip"  # "skip" | "merge" | "replace"


class CreateFieldsRequest(BaseModel):
    record_type: str
    fields: list[dict[str, str]]  # [{"name": "...", "field_type": "...", "label_de": "...", "label_en": "..."}]


@router.post("/upload")
async def upload_file(file: UploadFile, _: CurrentUser) -> dict:
    content = await file.read(MAX_SIZE + 1)
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="Datei zu groß (max 10 MB)")
    filename = (file.filename or "").lower()
    if filename.endswith(".xlsx"):
        headers, rows = importer_service.parse_excel(content)
    elif filename.endswith(".csv") or filename.endswith(".tsv"):
        headers, rows = importer_service.parse_csv(content)
    else:
        raise HTTPException(status_code=422, detail="Nur CSV, TSV und Excel (.xlsx) werden unterstützt")

    # Suggest field types for each column
    suggestions = importer_service.suggest_field_types(headers, rows)

    return {
        "headers": headers,
        "row_count": len(rows),
        "preview": rows[:5],
        "rows": rows,
        "suggestions": suggestions,
    }


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
async def run_import(body: ImportRequest, current_user: CurrentUser) -> dict:
    if body.record_type not in VALID_TYPES:
        raise HTTPException(status_code=422, detail=f"Ungültiger Typ: {body.record_type}")
    from katalon.workers.import_tasks import import_records_task
    task = import_records_task.delay(
        body.record_type,
        body.rows,
        body.mapping,
        idno_strategy=body.idno_strategy,
        upsert_strategy=body.upsert_strategy,
        user_id=str(current_user.id),
    )
    return {"status": "queued", "task_id": task.id}


@router.post("/create-fields", dependencies=[require_role("admin")])
async def create_fields(body: CreateFieldsRequest, db: DBDep) -> dict:
    """Create new field definitions on-the-fly for unmapped CSV columns."""
    if body.record_type not in VALID_TYPES:
        raise HTTPException(status_code=422, detail=f"Ungültiger Typ: {body.record_type}")

    created_fields: list[FieldDefinitionRead] = []
    for f in body.fields:
        name = f.get("name", "").strip()
        field_type = f.get("field_type", "text").strip()
        label_de = f.get("label_de", "").strip()
        label_en = f.get("label_en", "").strip()
        if not name:
            continue

        # Check if field already exists
        existing = await db.execute(
            select(FieldDefinition).where(
                FieldDefinition.target_type == body.record_type,
                FieldDefinition.name == name,
                FieldDefinition.is_deleted.is_(False),
            )
        )
        if existing.scalar_one_or_none():
            continue

        label: dict[str, str] = {}
        if label_de:
            label["de"] = label_de
        if label_en:
            label["en"] = label_en

        field = FieldDefinition(
            target_type=body.record_type,
            name=name,
            label=label,
            field_type=field_type,
            is_required=False,
            is_repeatable=False,
            sort_order=0,
        )
        db.add(field)
        await db.flush()
        created_fields.append(FieldDefinitionRead.model_validate(field))

    await db.commit()
    return {"created": len(created_fields), "fields": created_fields}


@router.get("/task/{task_id}")
async def task_status(task_id: str, _: CurrentUser) -> dict:
    from celery.result import AsyncResult
    from katalon.workers.celery_app import celery_app
    result = AsyncResult(task_id, app=celery_app)
    state = result.state
    if state == "SUCCESS":
        return {"state": state, "result": result.result}
    if state == "FAILURE":
        return {"state": state, "error": str(result.result)}
    # Include progress meta if available
    info = result.info if hasattr(result, "info") else None
    if isinstance(info, dict) and "current" in info:
        return {"state": state, "meta": info}
    return {"state": state}
