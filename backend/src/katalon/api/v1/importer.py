from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from katalon.core.dependencies import DBDep, require_admin_or_editor, require_role
from katalon.core.models import FieldDefinition, RecordSubtype
from katalon.core.schemas import FieldDefinitionRead
from katalon.services import importer_service
from katalon.services.importer import parse_file
from katalon.services.importer.formats.xml_format import XmlFormat
from katalon.services.schema_service import validate_metadata
from katalon.services.subtype_service import has_any_subtypes

router = APIRouter(prefix="/importer", tags=["importer"])

MAX_SIZE = 100 * 1024 * 1024  # 100 MB

_UPLOAD_TTL = 3600  # seconds — for both raw XML and parsed rows
_XML_UPLOAD_TTL = _UPLOAD_TTL  # keep alias used below

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
    mapping: dict[str, MappingEntry]   # selector -> {target, transforms?}
    # selector = CSV/Excel column header OR Clark-notation XPath for XML
    upload_id: str
    record_type: str = "object"
    subtype: str | None = None


class ImportRequest(MappingRequest):
    idno_strategy: str = "auto"   # "auto" | "column" | "skip"
    upsert_strategy: str = "skip"  # "skip" | "merge" | "replace"
    auto_publish: bool = False  # if True, publish records that pass validation after import
    fields_to_create: list[dict[str, Any]] = Field(default_factory=list)


class CreateFieldsRequest(BaseModel):
    record_type: str
    fields: list[dict[str, Any]]  # [{"name": "...", "field_type": "...", "label_de": "...", "label_en": "...", "is_repeatable": true/false}]


class XmlSelectorsRequest(BaseModel):
    upload_id: str
    record_xpath: str  # Clark-notation tag e.g. "{http://...}mods" or "*"


def _get_redis():
    import redis as redis_lib

    from katalon.config import settings
    return redis_lib.from_url(settings.redis_url, decode_responses=False)


def _store_rows(r, rows: list[dict]) -> str:
    import json
    upload_id = str(uuid.uuid4())
    r.setex(f"file_upload:{upload_id}", _UPLOAD_TTL, json.dumps(rows))
    return upload_id


def _load_rows(upload_id: str) -> list[dict]:
    import json
    r = _get_redis()
    data = r.get(f"file_upload:{upload_id}")
    if data is None:
        raise HTTPException(status_code=404, detail="Upload nicht gefunden oder abgelaufen (max 1 Stunde)")
    return json.loads(data)


@router.post("/upload")
async def upload_file(file: UploadFile, _=require_admin_or_editor()) -> dict:
    content = await file.read(MAX_SIZE + 1)
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="Datei zu groß (max 100 MB)")
    filename = file.filename or ""

    # XML gets a two-step flow: upload returns element levels, user picks record element
    xml_fmt = XmlFormat()
    if xml_fmt.sniff(content, filename):
        try:
            element_levels = xml_fmt.list_element_levels(content)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"XML konnte nicht geparst werden: {exc}") from exc
        upload_id = str(uuid.uuid4())
        r = _get_redis()
        r.setex(f"xml_upload:{upload_id}", _XML_UPLOAD_TTL, content)
        return {
            "source_type": "xml",
            "upload_id": upload_id,
            "element_levels": element_levels,
        }

    try:
        headers, rows, _ = parse_file(filename, content)
    except (ValueError, NotImplementedError):
        raise HTTPException(status_code=422, detail="Nur CSV, TSV, Excel (.xlsx) und XML werden unterstützt")

    r = _get_redis()
    upload_id = _store_rows(r, rows)
    suggestions = importer_service.suggest_field_types(headers, rows)
    source_type = "excel" if filename.lower().endswith((".xlsx", ".xls")) else "csv"
    return {
        "source_type": source_type,
        "upload_id": upload_id,
        "headers": headers,
        "row_count": len(rows),
        "preview": rows[:5],
        "suggestions": suggestions,
    }


@router.post("/xml-selectors")
async def xml_selectors(body: XmlSelectorsRequest, _=require_admin_or_editor()) -> dict:
    """Resolve selectors and rows for XML after the user has chosen the record element."""
    r = _get_redis()
    content = r.get(f"xml_upload:{body.upload_id}")
    if content is None:
        raise HTTPException(status_code=404, detail="Upload nicht gefunden oder abgelaufen (max 1 Stunde)")

    xml_fmt = XmlFormat()
    try:
        selectors = xml_fmt.list_selectors(content, record_xpath=body.record_xpath)
        rows = list(xml_fmt.parse_flat(content, record_xpath=body.record_xpath))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"XML konnte nicht verarbeitet werden: {exc}") from exc

    r = _get_redis()
    upload_id = _store_rows(r, rows)
    headers = [s.path for s in selectors]
    suggestions = importer_service.suggest_field_types(headers, rows)
    return {
        "source_type": "xml",
        "upload_id": upload_id,
        "headers": headers,
        "selectors": [{"path": s.path, "label": s.label, "sample": s.sample, "kind": s.kind} for s in selectors],
        "row_count": len(rows),
        "preview": rows[:5],
        "suggestions": suggestions,
    }


@router.post("/dry-run")
async def dry_run(body: MappingRequest, db: DBDep, _=require_admin_or_editor()) -> dict:
    if body.record_type not in VALID_TYPES:
        raise HTTPException(status_code=422, detail=f"Ungültiger Typ: {body.record_type}")

    # Validate subtype if provided
    if body.subtype:
        subtype_result = await db.execute(
            select(RecordSubtype).where(
                RecordSubtype.primary_type == body.record_type,
                RecordSubtype.name == body.subtype,
            )
        )
        if subtype_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=422, detail=f"Ungültiger Subtyp: {body.subtype}")

    result = await db.execute(
        select(FieldDefinition).where(
            FieldDefinition.target_type == body.record_type,
            FieldDefinition.is_deleted.is_(False),
        )
    )
    field_defs = {f.name: f for f in result.scalars().all()}

    rows = _load_rows(body.upload_id)

    # Build normalized mapping for dry_run: {csv_col -> {"target": ..., "transforms": [...]}}
    norm_mapping: dict[str, dict[str, Any]] = {}
    for k, v in body.mapping.items():
        norm_mapping[k] = {"target": v.target, "transforms": [t.model_dump() for t in v.transforms]}

    dry_result = importer_service.dry_run(rows, norm_mapping, field_defs)

    # Warn if type has subtypes but none was provided
    if not body.subtype and await has_any_subtypes(db, body.record_type):
        dry_result["warnings"].insert(0, {
            "row": None,
            "message": "Dieser Typ hat Subtypen — bitte einen Subtyp auswählen.",
        })

    # Run full schema validation per row (catches pid/relation/regex/required errors)
    from katalon.services.importer_service import apply_mapping
    all_records, _ = apply_mapping(rows, norm_mapping, field_defs)
    for i, metadata in enumerate(all_records):
        row_num = i + 2
        val_errors = await validate_metadata(db, body.record_type, metadata, body.subtype)
        for err in val_errors:
            dry_result["errors"].append({"row": row_num, "message": err})

    # Recompute valid count after full validation
    dry_result["valid"] = dry_result["total"] - len(dry_result["errors"])

    # Resolve vocab_stats against DB: count existing vs. new terms per vocab field
    vocab_warnings = []
    vocab_stats: dict[str, list[str]] = dry_result.pop("vocab_stats", {})
    for field_name, unique_values in vocab_stats.items():
        fd = field_defs.get(field_name)
        if not fd:
            continue
        vocab_id = (fd.settings or {}).get("vocabulary_id")
        if not vocab_id:
            continue
        from katalon.core.models import VocabularyTerm
        existing_terms_result = await db.execute(
            select(VocabularyTerm.term).where(
                VocabularyTerm.vocabulary_id == uuid.UUID(str(vocab_id)),
                VocabularyTerm.term.in_(unique_values),
            )
        )
        existing_set = {row[0] for row in existing_terms_result.all()}
        new_count = len([v for v in unique_values if v not in existing_set])
        label = (fd.label or {}).get("de") or field_name
        vocab_warnings.append({
            "field": field_name,
            "label": label,
            "unique_count": len(unique_values),
            "new_count": new_count,
            "high_cardinality": new_count > 100,
        })

    dry_result["vocab_warnings"] = vocab_warnings

    return dry_result


@router.post("/import")
async def run_import(body: ImportRequest, current_user=require_admin_or_editor()) -> dict:
    if body.record_type not in VALID_TYPES:
        raise HTTPException(status_code=422, detail=f"Ungültiger Typ: {body.record_type}")
    rows = _load_rows(body.upload_id)
    from katalon.workers.import_tasks import import_records_task
    # Serialize mapping for Celery (plain dict)
    serializable_mapping: dict[str, Any] = {}
    for k, v in body.mapping.items():
        serializable_mapping[k] = {"target": v.target, "transforms": [t.model_dump() for t in v.transforms]}
    task = import_records_task.delay(
        body.record_type,
        rows,
        serializable_mapping,
        idno_strategy=body.idno_strategy,
        upsert_strategy=body.upsert_strategy,
        auto_publish=body.auto_publish,
        user_id=str(current_user.id),
        subtype=body.subtype,
        fields_to_create=body.fields_to_create,
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


@router.post("/task/{task_id}/cancel")
async def cancel_task(task_id: str, _=require_admin_or_editor()) -> dict:
    r = _get_redis()
    r.setex(f"cancel:{task_id}", 3600, "1")
    return {"cancelled": True}


@router.get("/task/{task_id}")
async def task_status(task_id: str, _=require_admin_or_editor()) -> dict:
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
