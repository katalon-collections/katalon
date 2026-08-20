from __future__ import annotations

import json
import re
import uuid
from typing import Any, Literal, cast

from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from katalon.config import settings
from katalon.core.dependencies import DBDep, require_admin_or_editor, require_role
from katalon.core.models import FieldDefinition, ImportMapping, RecordSubtype, User
from katalon.core.schemas import FieldDefinitionRead, ImportMappingCreate, ImportMappingRead, ImportMappingUpdate
from katalon.services import importer_service
from katalon.services.importer import parse_file
from katalon.services.importer.formats.xml_format import XmlFormat
from katalon.services.schema_service import validate_metadata
from katalon.services.subtype_service import has_any_subtypes

router = APIRouter(prefix="/importer", tags=["importer"])

# Upload limits / staging TTL are configurable via Settings (see .env.example).
# Defaults: 500 MB upload size, 4 h TTL for the staged upload in Redis.

VALID_TYPES = {"object", "entity", "place", "occurrence"}
IMPORT_TASK_TTL_SECONDS = 24 * 60 * 60


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
    vocab_map: dict[str, str] = Field(default_factory=dict[str, Any])
    strict: bool = False
    # expression
    expression: str | None = None


class MappingEntry(BaseModel):
    target: str
    transforms: list[TransformConfig] = Field(default_factory=list[Any])


class MappingRequest(BaseModel):
    mapping: dict[str, MappingEntry] = Field(default_factory=dict[str, Any])  # selector -> {target, transforms?}
    mapping_id: uuid.UUID | None = None  # optional saved mapping template
    # selector = CSV/Excel column header OR Clark-notation XPath for XML
    upload_id: str
    record_type: str = "object"
    subtype: str | None = None
    media_selector: str | None = None
    # Fields the user will create on-the-fly. In dry-run these are merged as
    # transient (unpersisted) field defs so clustering/type-validation see them.
    fields_to_create: list[dict[str, Any]] = Field(default_factory=list[Any])


class ImportRequest(MappingRequest):
    idno_strategy: str = "auto"   # "auto" | "column" | "skip"
    upsert_strategy: str = "skip"  # "skip" | "merge" | "replace"
    auto_publish: bool = False  # if True, publish records that pass validation after import


class CreateFieldsRequest(BaseModel):
    record_type: str
    fields: list[dict[str, Any]]  # [{"name": "...", "field_type": "...", "label_de": "...", "label_en": "...", "is_repeatable": true/false}]


class XmlSelectorsRequest(BaseModel):
    upload_id: str
    record_xpath: str  # Clark-notation tag e.g. "{http://...}mods" or "*"


def _get_redis() -> Any:
    import redis as redis_lib

    from katalon.config import settings
    return redis_lib.from_url(settings.redis_url, decode_responses=False)  # type: ignore[no-untyped-call]  # redis stubs untyped


def _store_rows(r: Any, rows: list[dict[str, Any]]) -> str:
    import json
    upload_id = str(uuid.uuid4())
    r.setex(f"file_upload:{upload_id}", settings.importer_upload_ttl_seconds, json.dumps(rows))
    return upload_id


def _load_rows(upload_id: str) -> list[dict[str, Any]]:
    import json
    r = _get_redis()
    data = r.get(f"file_upload:{upload_id}")
    if data is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Upload nicht gefunden oder abgelaufen "
                f"(max {settings.importer_upload_ttl_seconds // 3600} Stunde(n))"
            ),
        )
    return cast(list[dict[str, Any]], json.loads(data))


_XML_PROLOG_RE = re.compile(rb"^\s*<\?xml[^>]*\?>")
_BATCH_ROOT_OPEN = b'<katalon:__batch__ xmlns:katalon="urn:katalon:import-batch">'
_BATCH_ROOT_CLOSE = b"</katalon:__batch__>"


def _combine_xml_files(contents: list[bytes]) -> bytes:
    """Wrap multiple single-record XML files (e.g. one LIDO record per file) into
    one synthetic document, so the existing element-level/record-xpath selection
    flow works unchanged: each file's root becomes a repeated child element.
    """
    bodies = [_XML_PROLOG_RE.sub(b"", c).strip() for c in contents]
    return _BATCH_ROOT_OPEN + b"".join(bodies) + _BATCH_ROOT_CLOSE


def _normalize_transform(value: Any) -> dict[str, Any]:
    if isinstance(value, TransformConfig):
        return value.model_dump()
    if isinstance(value, dict):
        return dict(value)
    return {}


def _normalize_mapping_entry(value: Any) -> dict[str, Any]:
    """Convert a MappingEntry model or a stored dict into normalized form."""
    if isinstance(value, MappingEntry):
        return {
            "target": value.target,
            "transforms": [_normalize_transform(t) for t in value.transforms],
        }
    if isinstance(value, dict):
        transforms = value.get("transforms") or []
        return {
            "target": value.get("target"),
            "transforms": [_normalize_transform(t) for t in transforms],
        }
    return {"target": str(value), "transforms": []}


def _normalize_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    return {k: _normalize_mapping_entry(v) for k, v in mapping.items()}


async def _resolve_mapping(
    body: MappingRequest,
    db: AsyncSession,
) -> tuple[dict[str, Any], str | None, str | None]:
    """Return normalized mapping, subtype and media_selector.

    If ``mapping_id`` is given, load the saved mapping and merge any inline
    ``mapping`` entries on top.  Inline ``subtype`` / ``media_selector`` win
    over the stored values.
    """
    mapping = _normalize_mapping(body.mapping or {})
    subtype = body.subtype
    media_selector = body.media_selector

    if body.mapping_id:
        result = await db.execute(
            select(ImportMapping).where(ImportMapping.id == body.mapping_id)
        )
        stored = result.scalar_one_or_none()
        if stored is None:
            raise HTTPException(status_code=404, detail="Import-Mapping nicht gefunden")
        if stored.record_type != body.record_type:
            raise HTTPException(
                status_code=422,
                detail="Import-Mapping passt nicht zum gewählten Datensatz-Typ",
            )
        stored_mapping = _normalize_mapping(stored.mapping or {})
        mapping = {**stored_mapping, **mapping}
        if subtype is None:
            subtype = stored.subtype
        if media_selector is None:
            media_selector = stored.media_selector

    return mapping, subtype, media_selector


@router.post(
    "/upload",
    summary="Upload one or more files for import (CSV, TSV, Excel, or XML)",
    responses={
        403: {"description": "Insufficient permissions"},
        413: {"description": "File too large"},
        422: {"description": "Unsupported file format or unparseable XML"},
    },
)
async def upload_file(
    files: list[UploadFile] = File(alias="file"),
    current_user: User = require_admin_or_editor(),
) -> dict[str, Any]:
    if not files:
        raise HTTPException(status_code=422, detail="Keine Datei hochgeladen")

    max_size = settings.importer_max_upload_size_mb * 1024 * 1024
    contents: list[bytes] = []
    total_size = 0
    for f in files:
        c = await f.read(max_size + 1)
        total_size += len(c)
        if total_size > max_size:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"Dateien zu groß (max {settings.importer_max_upload_size_mb} MB "
                    "insgesamt)"
                ),
            )
        contents.append(c)

    xml_fmt = XmlFormat()

    if len(files) > 1:
        # Multiple files: only supported for XML (one record per file, e.g. LIDO exports)
        for f, c in zip(files, contents, strict=True):
            if not xml_fmt.sniff(c, f.filename or ""):
                raise HTTPException(
                    status_code=422,
                    detail="Mehrere Dateien gleichzeitig werden nur für XML unterstützt (eine Datei pro Datensatz)",
                )
        content = _combine_xml_files(contents)
        filename = "batch.xml"
    else:
        content = contents[0]
        filename = files[0].filename or ""

    # XML gets a two-step flow: upload returns element levels, user picks record element
    if xml_fmt.sniff(content, filename):
        try:
            element_levels = xml_fmt.list_element_levels(content)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"XML konnte nicht geparst werden: {exc}") from exc
        upload_id = str(uuid.uuid4())
        r = _get_redis()
        r.setex(f"xml_upload:{upload_id}", settings.importer_upload_ttl_seconds, content)
        return {
            "source_type": "xml",
            "upload_id": upload_id,
            "element_levels": element_levels,
        }

    if len(files) > 1:
        raise HTTPException(
            status_code=422,
            detail="Mehrere Dateien gleichzeitig werden nur für XML unterstützt (eine Datei pro Datensatz)",
        )

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


@router.post(
    "/xml-selectors",
    summary="Resolve XML selectors and rows after choosing the record element",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Upload not found or expired"},
        422: {"description": "XML could not be processed"},
    },
)
async def xml_selectors(body: XmlSelectorsRequest, current_user: User = require_admin_or_editor()) -> dict[str, Any]:
    """Resolve selectors and rows for XML after the user has chosen the record element."""
    r = _get_redis()
    content = r.get(f"xml_upload:{body.upload_id}")
    if content is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Upload nicht gefunden oder abgelaufen "
                f"(max {settings.importer_upload_ttl_seconds // 3600} Stunde(n))"
            ),
        )

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


@router.post(
    "/dry-run",
    summary="Preview an import without persisting records",
    responses={
        403: {"description": "Insufficient permissions"},
        422: {"description": "Invalid record type or subtype"},
        404: {"description": "Upload not found or expired"},
    },
)
async def dry_run(body: MappingRequest, db: DBDep, current_user: User = require_admin_or_editor()) -> dict[str, Any]:
    if body.record_type not in VALID_TYPES:
        raise HTTPException(status_code=422, detail=f"Ungültiger Typ: {body.record_type}")

    mapping, subtype, media_selector = await _resolve_mapping(body, db)

    if media_selector and body.record_type != "object":
        raise HTTPException(status_code=422, detail="Medienzuordnung ist nur für Objekte möglich")

    # Validate subtype if provided
    if subtype:
        subtype_result = await db.execute(
            select(RecordSubtype).where(
                RecordSubtype.primary_type == body.record_type,
                RecordSubtype.name == subtype,
            )
        )
        if subtype_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=422, detail=f"Ungültiger Subtyp: {subtype}")

    result = await db.execute(
        select(FieldDefinition).where(
            FieldDefinition.target_type == body.record_type,
            FieldDefinition.is_deleted.is_(False),
        )
    )
    field_defs = {f.name: f for f in result.scalars().all()}

    # Merge on-the-fly fields as transient (not persisted) defs so clustering,
    # type- and required-validation see them in the preview. DB fields win on name clash.
    for f in body.fields_to_create:
        name = str(f.get("name", "")).strip()
        if not name or name in field_defs:
            continue
        label: dict[str, str] = {}
        if f.get("label_de"):
            label["de"] = str(f["label_de"]).strip()
        if f.get("label_en"):
            label["en"] = str(f["label_en"]).strip()
        field_defs[name] = FieldDefinition(
            target_type=body.record_type,
            name=name,
            label=label,
            field_type=str(f.get("field_type", "text")).strip(),
            is_required=False,
            is_repeatable=bool(f.get("is_repeatable", False)),
            sort_order=0,
        )

    rows = _load_rows(body.upload_id)

    # mapping is already normalized to {selector -> {"target": ..., "transforms": [...]}}
    norm_mapping = mapping

    dry_result = importer_service.dry_run(rows, norm_mapping, field_defs)

    # Warn if type has subtypes but none was provided
    if not subtype and await has_any_subtypes(db, body.record_type):
        dry_result["warnings"].insert(0, {
            "row": None,
            "message": "Dieser Typ hat Subtypen — bitte einen Subtyp auswählen.",
        })

    # Run full schema validation per row (catches pid/relation/regex/required errors)
    from katalon.services.importer_service import apply_mapping
    all_records, _ = apply_mapping(rows, norm_mapping, field_defs)
    for i, metadata in enumerate(all_records):
        row_num = i + 2
        val_errors = await validate_metadata(db, body.record_type, metadata, subtype)
        for err in val_errors:
            dry_result["errors"].append({"row": row_num, "message": err})

    if media_selector:
        from katalon.services.media_batch_import_service import media_references_for_rows

        _, media_stats = media_references_for_rows(rows, media_selector)
        dry_result["media_references"] = media_stats
        if not media_stats["selector_found"]:
            dry_result["errors"].append({
                "row": None,
                "message": f"Medienzuordnung '{media_selector}' wurde nicht gefunden",
            })
        else:
            for conflict in media_stats["conflicts"]:
                for row_num in conflict["rows"]:
                    dry_result["errors"].append({
                        "row": row_num,
                        "message": (
                            f"Dateiname '{conflict['filename']}' ist mehreren Datensätzen zugeordnet"
                        ),
                    })
    else:
        dry_result["media_references"] = None

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
        label_text = (fd.label or {}).get("de") or field_name
        vocab_warnings.append({
            "field": field_name,
            "label": label_text,
            "unique_count": len(unique_values),
            "new_count": new_count,
            "high_cardinality": new_count > 100,
        })

    dry_result["vocab_warnings"] = vocab_warnings

    # Group fuzzy-clustered vocab variant suggestions by field, with field labels attached
    vocab_clusters_raw: dict[str, list[dict[str, Any]]] = dry_result.pop("vocab_clusters", {})
    vocab_clusters = []
    for field_name, clusters in vocab_clusters_raw.items():
        fd = field_defs.get(field_name)
        label_text = ((fd.label or {}).get("de") or field_name) if fd else field_name
        vocab_clusters.append({"field": field_name, "label": label_text, "clusters": clusters})
    dry_result["vocab_clusters"] = vocab_clusters

    return dry_result


@router.post(
    "/import",
    summary="Queue a background import job",
    responses={
        403: {"description": "Insufficient permissions"},
        422: {"description": "Invalid record type"},
        404: {"description": "Upload not found or expired"},
        503: {"description": "Background task queue unavailable (broker down)"},
    },
)
async def run_import(body: ImportRequest, db: DBDep, current_user: User = require_admin_or_editor()) -> dict[str, Any]:
    if body.record_type not in VALID_TYPES:
        raise HTTPException(status_code=422, detail=f"Ungültiger Typ: {body.record_type}")

    mapping, subtype, media_selector = await _resolve_mapping(body, db)

    if media_selector and body.record_type != "object":
        raise HTTPException(status_code=422, detail="Medienzuordnung ist nur für Objekte möglich")
    rows = _load_rows(body.upload_id)
    if media_selector:
        from katalon.services.media_batch_import_service import media_references_for_rows

        _, media_stats = media_references_for_rows(rows, media_selector)
        if not media_stats["selector_found"]:
            raise HTTPException(
                status_code=422,
                detail=f"Medienzuordnung '{media_selector}' wurde nicht gefunden",
            )
        if media_stats["conflicts"]:
            raise HTTPException(
                status_code=422,
                detail="Ein Dateiname ist mehreren Datensätzen zugeordnet",
            )
    from katalon.workers.import_tasks import import_records_task
    # mapping is already a normalized, serializable dict
    from katalon.workers.enqueue import enqueue_or_503
    task_id = enqueue_or_503(
        import_records_task,
        body.record_type,
        rows,
        mapping,
        idno_strategy=body.idno_strategy,
        upsert_strategy=body.upsert_strategy,
        auto_publish=body.auto_publish,
        user_id=str(current_user.id),
        subtype=subtype,
        fields_to_create=body.fields_to_create,
        media_selector=media_selector,
    )
    _get_redis().setex(f"import_task:{task_id}", IMPORT_TASK_TTL_SECONDS, "1")
    return {"status": "queued", "task_id": task_id}


@router.get(
    "/mappings",
    response_model=list[ImportMappingRead],
    summary="List saved import mappings",
    responses={403: {"description": "Insufficient permissions"}},
)
async def list_import_mappings(
    db: DBDep,
    record_type: str | None = None,
    current_user: User = require_admin_or_editor(),
) -> list[ImportMapping]:
    """Return saved import mappings, optionally filtered by record type."""
    query = select(ImportMapping).order_by(ImportMapping.updated_at.desc())
    if record_type:
        if record_type not in VALID_TYPES:
            raise HTTPException(status_code=422, detail=f"Ungültiger Typ: {record_type}")
        query = query.where(ImportMapping.record_type == record_type)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.post(
    "/mappings",
    response_model=ImportMappingRead,
    status_code=201,
    summary="Save an import mapping",
    responses={
        403: {"description": "Insufficient permissions"},
        422: {"description": "Invalid record type or missing name"},
    },
)
async def create_import_mapping(
    body: ImportMappingCreate,
    db: DBDep,
    current_user: User = require_admin_or_editor(),
) -> ImportMapping:
    """Persist an import mapping so it can be reused by ID."""
    if body.record_type not in VALID_TYPES:
        raise HTTPException(status_code=422, detail=f"Ungültiger Typ: {body.record_type}")
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Name darf nicht leer sein")

    mapping = ImportMapping(
        name=name,
        record_type=body.record_type,
        subtype=body.subtype,
        media_selector=body.media_selector,
        mapping=_normalize_mapping(body.mapping or {}),
        created_by=current_user.id,
    )
    db.add(mapping)
    await db.flush()
    await db.refresh(mapping)
    return mapping


@router.get(
    "/mappings/{mapping_id}",
    response_model=ImportMappingRead,
    summary="Get a saved import mapping",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Mapping not found"},
    },
)
async def get_import_mapping(
    mapping_id: uuid.UUID,
    db: DBDep,
    current_user: User = require_admin_or_editor(),
) -> ImportMapping:
    result = await db.execute(select(ImportMapping).where(ImportMapping.id == mapping_id))
    mapping = result.scalar_one_or_none()
    if mapping is None:
        raise HTTPException(status_code=404, detail="Import-Mapping nicht gefunden")
    return mapping


@router.put(
    "/mappings/{mapping_id}",
    response_model=ImportMappingRead,
    summary="Update a saved import mapping",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Mapping not found"},
        422: {"description": "Invalid payload"},
    },
)
async def update_import_mapping(
    mapping_id: uuid.UUID,
    body: ImportMappingUpdate,
    db: DBDep,
    current_user: User = require_admin_or_editor(),
) -> ImportMapping:
    result = await db.execute(select(ImportMapping).where(ImportMapping.id == mapping_id))
    mapping = result.scalar_one_or_none()
    if mapping is None:
        raise HTTPException(status_code=404, detail="Import-Mapping nicht gefunden")

    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="Name darf nicht leer sein")
        mapping.name = name
    if body.subtype is not None:
        mapping.subtype = body.subtype
    if body.media_selector is not None:
        mapping.media_selector = body.media_selector
    if body.mapping is not None:
        mapping.mapping = _normalize_mapping(body.mapping)

    await db.flush()
    await db.refresh(mapping)
    return mapping


@router.delete(
    "/mappings/{mapping_id}",
    status_code=204,
    summary="Delete a saved import mapping",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Mapping not found"},
    },
)
async def delete_import_mapping(
    mapping_id: uuid.UUID,
    db: DBDep,
    current_user: User = require_admin_or_editor(),
) -> None:
    result = await db.execute(select(ImportMapping).where(ImportMapping.id == mapping_id))
    mapping = result.scalar_one_or_none()
    if mapping is None:
        raise HTTPException(status_code=404, detail="Import-Mapping nicht gefunden")
    await db.delete(mapping)
    await db.commit()


@router.get(
    "/mappings/{mapping_id}/download",
    summary="Download a saved import mapping as JSON",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Mapping not found"},
    },
)
async def download_import_mapping(
    mapping_id: uuid.UUID,
    db: DBDep,
    current_user: User = require_admin_or_editor(),
) -> Response:
    result = await db.execute(select(ImportMapping).where(ImportMapping.id == mapping_id))
    mapping = result.scalar_one_or_none()
    if mapping is None:
        raise HTTPException(status_code=404, detail="Import-Mapping nicht gefunden")

    return Response(
        content=json.dumps(mapping.mapping, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="import-mapping-{mapping.id}.json"',
        },
    )


@router.post(
    "/create-fields",
    dependencies=[require_role("admin")],
    summary="Create field definitions on-the-fly for unmapped import columns",
    responses={
        403: {"description": "Insufficient permissions"},
        422: {"description": "Invalid record type"},
    },
)
async def create_fields(body: CreateFieldsRequest, db: DBDep) -> dict[str, Any]:
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


@router.post(
    "/task/{task_id}/cancel",
    summary="Request cancellation of a running import task",
    responses={403: {"description": "Insufficient permissions"}},
)
async def cancel_task(task_id: str, current_user: User = require_admin_or_editor()) -> dict[str, Any]:
    r = _get_redis()
    r.setex(f"cancel:{task_id}", 3600, "1")
    return {"cancelled": True}


@router.get(
    "/task/{task_id}",
    summary="Get the status of an import task",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Import task not found or expired"},
    },
)
async def task_status(task_id: str, current_user: User = require_admin_or_editor()) -> dict[str, Any]:
    from celery.result import AsyncResult

    from katalon.workers.celery_app import celery_app
    result: AsyncResult[Any] = AsyncResult(task_id, app=celery_app)
    state = result.state
    if state == "PENDING" and not _get_redis().exists(f"import_task:{task_id}"):
        raise HTTPException(status_code=404, detail="Import-Aufgabe nicht gefunden oder abgelaufen")
    if state == "SUCCESS":
        return {"state": state, "result": result.result}
    if state == "FAILURE":
        return {"state": state, "error": str(result.result)}
    # Include progress meta if available
    info = result.info if hasattr(result, "info") else None
    if isinstance(info, dict) and "current" in info:
        return {"state": state, "meta": info}
    return {"state": state}
