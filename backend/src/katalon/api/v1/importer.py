from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from typing import Literal, Any

from katalon.core.dependencies import CurrentUser, DBDep, require_role
from katalon.core.models import FieldDefinition
from katalon.services import importer_service
from katalon.core.schemas import FieldDefinitionCreate, FieldDefinitionRead

router = APIRouter(prefix="/importer", tags=["importer"])

MAX_SIZE = 10 * 1024 * 1024  # 10 MB (matches frontend limit)

VALID_TYPES = {"object", "entity", "place", "occurrence"}


class TransformConfig(BaseModel):
    type: Literal["split", "replace", "regex_extract", "trim", "vocab_map", "expression"]
    # split
    delimiter: str | None = None
    filter_empty: bool = True
    # replace
    search: str | None = None
    replace: str | None = None
    case_sensitive: bool = True
    # regex_extract
    pattern: str | None = None
    group: int = 0
    # trim
    trim: bool = True
    # vocab_map
    vocab_map: dict[str, str] = Field(default_factory=dict)
    strict: bool = False
    # expression
    expression: str | None = None


class MappingEntry(BaseModel):
    target: str
    transforms: list[TransformConfig] = Field(default_factory=list)


class MappingRequest(BaseModel):
    mapping: dict[str, MappingEntry]   # csv_column -> {target, transforms?}
    rows: list[dict[str, str]]
    record_type: str = "object"


class ImportRequest(MappingRequest):
    idno_strategy: str = "auto"   # "auto" | "column" | "skip"
    upsert_strategy: str = "skip"  # "skip" | "merge" | "replace"
    auto_publish: bool = False  # if True, publish records that pass validation after import


class CreateFieldsRequest(BaseModel):
    record_type: str
    fields: list[dict[str, Any]]  # [{"name": "...", "field_type": "...", "label_de": "...", "label_en": "...", "is_repeatable": true/false}]


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
    # Build normalized mapping for dry_run: {csv_col -> {"target": ..., "transforms": [...]}}
    norm_mapping: dict[str, dict[str, Any]] = {}
    for k, v in body.mapping.items():
        norm_mapping[k] = {"target": v.target, "transforms": [t.model_dump() for t in v.transforms]}
    return importer_service.dry_run(body.rows, norm_mapping, field_defs)


@router.post("/import")
async def run_import(body: ImportRequest, current_user: CurrentUser) -> dict:
    if body.record_type not in VALID_TYPES:
        raise HTTPException(status_code=422, detail=f"Ungültiger Typ: {body.record_type}")
    from katalon.workers.import_tasks import import_records_task
    # Serialize mapping for Celery (plain dict)
    serializable_mapping: dict[str, Any] = {}
    for k, v in body.mapping.items():
        serializable_mapping[k] = {"target": v.target, "transforms": [t.model_dump() for t in v.transforms]}
    task = import_records_task.delay(
        body.record_type,
        body.rows,
        serializable_mapping,
        idno_strategy=body.idno_strategy,
        upsert_strategy=body.upsert_strategy,
        auto_publish=body.auto_publish,
        user_id=str(current_user.id),
    )
    return {"status": "queued", "task_id": task.id}


@router.post("/create-fields", dependencies=[require_role("admin")])
async def create_fields(body: CreateFieldsRequest, db: DBDep) -> dict:
    """Create new field definitions on-the-fly for unmapped CSV columns.

    If a field was soft-deleted, it will be undeleted and updated.
    """
    if body.record_type not in VALID_TYPES:
        raise HTTPException(status_code=422, detail=f"Ungültiger Typ: {body.record_type}")

    created_fields: list[FieldDefinitionRead] = []
    restored_names: list[str] = []

    for f in body.fields:
        name = f.get("name", "").strip()
        field_type = f.get("field_type", "text").strip()
        label_de = f.get("label_de", "").strip()
        label_en = f.get("label_en", "").strip()
        is_repeatable = bool(f.get("is_repeatable", False))
        if not name:
            continue

        # Check if field already exists (including soft-deleted)
        existing_result = await db.execute(
            select(FieldDefinition).where(
                FieldDefinition.target_type == body.record_type,
                FieldDefinition.name == name,
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            if existing.is_deleted:
                # Undelete and update the soft-deleted field
                existing.is_deleted = False
                existing.field_type = field_type
                existing.is_repeatable = is_repeatable
                if label_de:
                    existing.label = {**existing.label, "de": label_de}
                if label_en:
                    existing.label = {**existing.label, "en": label_en}
                await db.flush()
                restored_names.append(name)
                created_fields.append(FieldDefinitionRead.model_validate(existing))
            else:
                # Field already exists and is active — skip
                restored_names.append(name)
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
            is_repeatable=is_repeatable,
            sort_order=0,
        )
        db.add(field)
        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            restored_names.append(name)
            continue
        created_fields.append(FieldDefinitionRead.model_validate(field))

    await db.commit()
    return {"created": len(created_fields), "fields": created_fields, "restored": restored_names}


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
