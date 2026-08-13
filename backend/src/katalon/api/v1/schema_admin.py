import json
import uuid
from collections import defaultdict

import yaml
from fastapi import APIRouter, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import or_, select

from katalon.core.dependencies import DBDep, require_role
from katalon.core.models import AuthoritySource, FieldDefinition, Vocabulary, VocabularyTerm
from katalon.core.schemas import FieldDefinitionCreate, FieldDefinitionRead
from katalon.services import authority_service
from katalon.services.subtype_service import ensure_subtype_exists

SCHEMA_TARGET_TYPES = {"object", "entity", "place", "occurrence", "procedure", "vocabulary_term"}
VOCABULARY_TERM_FIELD_TYPES = {"text", "number", "boolean", "authority"}


def _validate_schema_target_type(target_type: str) -> None:
    if target_type not in SCHEMA_TARGET_TYPES:
        raise HTTPException(status_code=422, detail="Ungültiger Primärtyp.")


async def _ensure_schema_subtype_exists(db: DBDep, target_type: str, subtype: str | None) -> None:
    if target_type == "vocabulary_term":
        if not subtype:
            raise HTTPException(status_code=422, detail="Vokabular ist erforderlich.")
        try:
            vocab_id = uuid.UUID(subtype)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Ungültige Vokabular-ID.") from exc
        if not await db.get(Vocabulary, vocab_id):
            raise HTTPException(status_code=422, detail="Vokabular nicht gefunden.")
        return
    await ensure_subtype_exists(db, target_type, subtype)


async def _validate_field_settings(db: DBDep, data: FieldDefinitionCreate) -> None:
    if (
        data.target_type == "vocabulary_term"
        and data.field_type not in VOCABULARY_TERM_FIELD_TYPES
    ):
        raise HTTPException(
            status_code=422,
            detail="Dieser Feldtyp ist für Vokabularterme nicht erlaubt.",
        )

    if data.field_type == "authority":
        source = data.settings.get("source")
        db_sources = list((await db.execute(select(AuthoritySource))).scalars().all())
        enabled = (
            {item.id for item in db_sources if item.is_enabled}
            if db_sources
            else set(authority_service.list_sources())
        )
        if source not in enabled:
            raise HTTPException(
                status_code=422,
                detail="Unbekannte oder deaktivierte Authority-Quelle.",
            )

    vocab_id = data.settings.get("vocabulary_id")
    expected_kind = "term"
    if data.field_type == "relation":
        vocab_id = data.settings.get("relation_type_vocab")
        expected_kind = "relation"
        if not vocab_id:
            raise HTTPException(
                status_code=422,
                detail="Ein Relationsfeld benötigt ein Relationstyp-Vokabular.",
            )
    if not vocab_id:
        return
    try:
        vocab = await db.get(Vocabulary, uuid.UUID(str(vocab_id)))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Ungültige Vokabular-ID.") from exc
    if not vocab or vocab.kind != expected_kind:
        raise HTTPException(
            status_code=422,
            detail=f"Vokabular muss vom Typ '{expected_kind}' sein.",
        )
    fixed_relation_type = data.settings.get("fixed_relation_type")
    if data.field_type == "relation":
        target_type = data.settings.get("target_type")
        matching_terms = select(VocabularyTerm.id).where(
            VocabularyTerm.vocabulary_id == vocab.id,
            (VocabularyTerm.applies_from == []) | VocabularyTerm.applies_from.contains([data.target_type]),
            (VocabularyTerm.applies_to == []) | VocabularyTerm.applies_to.contains([target_type]),
        )
        if fixed_relation_type:
            matching_terms = matching_terms.where(VocabularyTerm.term == fixed_relation_type)
        if await db.scalar(matching_terms.limit(1)) is None:
            if fixed_relation_type:
                detail = "Der feste Relationstyp ist für Quell- und Zieltyp nicht erlaubt."
            else:
                detail = "Das Relationstyp-Vokabular enthält keinen Typ für diese Quell- und Zieltypkombination."
            raise HTTPException(status_code=422, detail=detail)


def _fd_read(f: FieldDefinition, children: list[FieldDefinitionRead] | None = None) -> FieldDefinitionRead:
    """Validate a FieldDefinition ORM object into FieldDefinitionRead without triggering lazy loads."""
    cols = {attr.key: getattr(f, attr.key) for attr in sa_inspect(type(f)).mapper.column_attrs}
    cols["children"] = children or []
    return FieldDefinitionRead.model_validate(cols)

router = APIRouter(prefix="/schema", tags=["schema"])


def _enqueue_reindex(target_type: str) -> None:
    """Fire-and-forget: enqueue a type-specific ES reindex after schema changes."""
    if target_type == "vocabulary_term":
        return
    from katalon.workers.enqueue import enqueue
    from katalon.workers.index_tasks import bulk_reindex_type_task
    enqueue(bulk_reindex_type_task, target_type)


class ImportResult(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: list[str]
    fields: list[FieldDefinitionRead]


async def _embed_children(
    db: DBDep, target_type: str, top_fields: list[FieldDefinition]
) -> list[FieldDefinitionRead]:
    """Load sub-fields for all group fields and embed them as children."""
    group_ids = [f.id for f in top_fields if f.field_type == "group"]
    children_map: dict[uuid.UUID, list[FieldDefinition]] = defaultdict(list)
    if group_ids:
        sub_result = await db.execute(
            select(FieldDefinition).where(
                FieldDefinition.target_type == target_type,
                FieldDefinition.parent_id.in_(group_ids),
                FieldDefinition.is_deleted.is_(False),
            ).order_by(FieldDefinition.sort_order)
        )
        for sf in sub_result.scalars().all():
            children_map[sf.parent_id].append(sf)

    out: list[FieldDefinitionRead] = []
    for f in top_fields:
        children = [_fd_read(c) for c in children_map.get(f.id, [])] if f.field_type == "group" else []
        out.append(_fd_read(f, children))
    return out


@router.get(
    "/{target_type}",
    response_model=list[FieldDefinitionRead],
    summary="List field definitions for a target type",
    responses={422: {"description": "Invalid target type or subtype"}},
)
async def list_fields(
    target_type: str,
    db: DBDep,
    subtype: str | None = Query(default=None, description="Filter to generic + this subtype"),
    include_deleted: bool = Query(False, description="Include soft-deleted fields"),
) -> list[FieldDefinitionRead]:
    _validate_schema_target_type(target_type)
    if subtype is not None:
        await _ensure_schema_subtype_exists(db, target_type, subtype)
    q = select(FieldDefinition).where(
        FieldDefinition.target_type == target_type,
        FieldDefinition.parent_id.is_(None),  # top-level only; sub-fields embedded via children
    )
    if subtype:
        q = q.where(
            or_(FieldDefinition.target_subtype.is_(None), FieldDefinition.target_subtype == subtype)
        )
    if not include_deleted:
        q = q.where(FieldDefinition.is_deleted.is_(False))
    result = await db.execute(q.order_by(FieldDefinition.sort_order))
    top_fields = list(result.scalars().all())
    return await _embed_children(db, target_type, top_fields)


async def _validate_parent(db: DBDep, parent_id: uuid.UUID, field_type: str) -> None:
    """Validate parent_id: parent must exist, be a group field, and sub-fields cannot be groups."""
    if field_type == "group":
        raise HTTPException(
            status_code=422,
            detail="Verschachtelte Containerfelder (Gruppe in Gruppe) sind nicht erlaubt.",
        )
    result = await db.execute(
        select(FieldDefinition).where(
            FieldDefinition.id == parent_id,
            FieldDefinition.is_deleted.is_(False),
        )
    )
    parent = result.scalar_one_or_none()
    if not parent:
        raise HTTPException(status_code=404, detail="Übergeordnetes Feld nicht gefunden.")
    if parent.field_type != "group":
        raise HTTPException(
            status_code=422,
            detail="Sub-Felder können nur unter einem Containerfeld (Gruppe) angelegt werden.",
        )


@router.post(
    "",
    response_model=FieldDefinitionRead,
    status_code=201,
    dependencies=[require_role("admin")],
    summary="Create a new field definition",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Parent field not found"},
        422: {"description": "Invalid field name, target type, subtype, parent, or settings"},
    },
)
async def create_field(data: FieldDefinitionCreate, db: DBDep) -> FieldDefinitionRead:
    if not data.name or not data.name.strip():
        raise HTTPException(status_code=422, detail="Feldname darf nicht leer sein")
    _validate_schema_target_type(data.target_type)
    if data.parent_id:
        await _validate_parent(db, data.parent_id, data.field_type)
    else:
        await _ensure_schema_subtype_exists(db, data.target_type, data.target_subtype)
    await _validate_field_settings(db, data)
    field = FieldDefinition(**data.model_dump())
    db.add(field)
    await db.flush()
    _enqueue_reindex(data.target_type)
    return _fd_read(field)


@router.put(
    "/{field_id}",
    response_model=FieldDefinitionRead,
    dependencies=[require_role("admin")],
    summary="Update an existing field definition",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Field definition or parent field not found"},
        422: {"description": "Invalid field name, target type, subtype, parent, or settings"},
    },
)
async def update_field(
    field_id: uuid.UUID, data: FieldDefinitionCreate, db: DBDep
) -> FieldDefinitionRead:
    if not data.name or not data.name.strip():
        raise HTTPException(status_code=422, detail="Feldname darf nicht leer sein")
    _validate_schema_target_type(data.target_type)
    if data.parent_id:
        await _validate_parent(db, data.parent_id, data.field_type)
    else:
        await _ensure_schema_subtype_exists(db, data.target_type, data.target_subtype)
    await _validate_field_settings(db, data)
    result = await db.execute(
        select(FieldDefinition).where(
            FieldDefinition.id == field_id, FieldDefinition.is_deleted.is_(False)
        )
    )
    field = result.scalar_one_or_none()
    if not field:
        raise HTTPException(status_code=404, detail="Felddefinition nicht gefunden")
    old_is_facet = field.is_facet
    old_settings = field.settings or {}
    for k, v in data.model_dump().items():
        setattr(field, k, v)
    await db.flush()
    inherited_settings_changed = field.field_type == "relation" and any(
        old_settings.get(key) != field.settings.get(key)
        for key in ("target_type", "fixed_relation_type", "inherited_fields")
    )
    if field.is_facet != old_is_facet or inherited_settings_changed:
        _enqueue_reindex(field.target_type)
    return _fd_read(field)


@router.delete(
    "/{field_id}",
    status_code=204,
    dependencies=[require_role("admin")],
    summary="Soft-delete a field definition",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Field definition not found"},
        422: {"description": "Field 'label' is a system field and cannot be deleted"},
    },
)
async def delete_field(field_id: uuid.UUID, db: DBDep) -> None:
    result = await db.execute(
        select(FieldDefinition).where(
            FieldDefinition.id == field_id, FieldDefinition.is_deleted.is_(False)
        )
    )
    field = result.scalar_one_or_none()
    if not field:
        raise HTTPException(status_code=404, detail="Felddefinition nicht gefunden")
    if field.name == "label":
        raise HTTPException(status_code=422, detail="Das Feld 'label' ist ein Systemfeld und kann nicht gelöscht werden.")
    field.is_deleted = True
    target_type = field.target_type
    await db.flush()
    _enqueue_reindex(target_type)


@router.post(
    "/{field_id}/restore",
    response_model=FieldDefinitionRead,
    dependencies=[require_role("admin")],
    summary="Restore a soft-deleted field definition",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Deleted field definition not found"},
    },
)
async def restore_field(field_id: uuid.UUID, db: DBDep) -> FieldDefinitionRead:
    result = await db.execute(
        select(FieldDefinition).where(
            FieldDefinition.id == field_id, FieldDefinition.is_deleted.is_(True)
        )
    )
    field = result.scalar_one_or_none()
    if not field:
        raise HTTPException(status_code=404, detail="Gelöschte Felddefinition nicht gefunden")
    field.is_deleted = False
    target_type = field.target_type
    await db.flush()
    _enqueue_reindex(target_type)
    return _fd_read(field)


@router.post(
    "/import",
    response_model=ImportResult,
    status_code=200,
    dependencies=[require_role("admin")],
    summary="Import field definitions from a YAML or JSON file",
    responses={
        403: {"description": "Insufficient permissions"},
        422: {"description": "File could not be parsed or has an invalid format"},
    },
)
async def import_schema(
    file: UploadFile,
    db: DBDep,
    dry_run: bool = Query(False, description="Preview changes without writing to DB"),
    overwrite: bool = Query(False, description="Overwrite existing fields"),
) -> ImportResult:
    """Import field definitions from a YAML or JSON file.

    Expected format:
      target_type: object
      fields:
        - name: title
          label: {de: Titel, en: Title}
          field_type: text
          is_required: true
    """
    content = await file.read()
    try:
        filename = file.filename or ""
        if filename.endswith(".yaml") or filename.endswith(".yml"):
            data = yaml.safe_load(content)
        else:
            data = json.loads(content)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Datei konnte nicht geparst werden: {exc}")

    if not isinstance(data, dict) or "target_type" not in data or "fields" not in data:
        raise HTTPException(
            status_code=422,
            detail="Ungültiges Format. Erwartet: {target_type, fields: [...]}",
        )

    target_type: str = data["target_type"]
    _validate_schema_target_type(target_type)
    raw_fields: list = data.get("fields", [])

    if not isinstance(raw_fields, list):
        raise HTTPException(status_code=422, detail="'fields' muss eine Liste sein")

    # Load existing fields (by target_type + name) for upsert logic
    existing_result = await db.execute(
        select(FieldDefinition).where(FieldDefinition.target_type == target_type)
    )
    existing_map: dict[tuple[str | None, str], FieldDefinition] = {
        (f.target_subtype, f.name): f for f in existing_result.scalars().all()
    }

    created = 0
    updated = 0
    skipped = 0
    errors: list[str] = []
    result_fields: list[FieldDefinition] = []

    for idx, raw in enumerate(raw_fields):
        if not isinstance(raw, dict):
            errors.append(f"Feld #{idx}: kein Objekt")
            continue
        name = raw.get("name", "").strip()
        if not name:
            errors.append(f"Feld #{idx}: 'name' fehlt oder leer")
            continue

        field_data = FieldDefinitionCreate(
            target_type=target_type,
            target_subtype=raw.get("target_subtype"),
            name=name,
            label=raw.get("label", {}),
            field_type=raw.get("field_type", "text"),
            is_required=raw.get("is_required", False),
            is_repeatable=raw.get("is_repeatable", False),
            sort_order=raw.get("sort_order", idx),
            settings=raw.get("settings", {}),
        )
        await _ensure_schema_subtype_exists(db, target_type, field_data.target_subtype)
        await _validate_field_settings(db, field_data)

        key = (field_data.target_subtype, name)
        if key in existing_map:
            existing = existing_map[key]
            if not overwrite:
                skipped += 1
                result_fields.append(existing)
                continue
            if not dry_run:
                for k, v in field_data.model_dump().items():
                    setattr(existing, k, v)
                existing.is_deleted = False
            updated += 1
            result_fields.append(existing)
        else:
            field = FieldDefinition(**field_data.model_dump())
            if not dry_run:
                db.add(field)
                await db.flush()
            created += 1
            result_fields.append(field)

    if not dry_run and (created > 0 or updated > 0):
        await db.flush()
        _enqueue_reindex(target_type)

    return ImportResult(
        created=created,
        updated=updated,
        skipped=skipped,
        errors=errors,
        fields=[_fd_read(f) for f in result_fields],
    )
