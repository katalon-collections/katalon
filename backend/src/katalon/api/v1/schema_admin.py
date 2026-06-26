import json
import uuid
from collections import defaultdict

import yaml
from fastapi import APIRouter, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import or_, select

from katalon.core.dependencies import DBDep, require_role
from katalon.core.models import FieldDefinition
from katalon.core.schemas import FieldDefinitionCreate, FieldDefinitionRead
from katalon.services.subtype_service import ensure_subtype_exists


SCHEMA_TARGET_TYPES = {"object", "entity", "place", "occurrence", "procedure"}
PROCEDURE_TYPES = {"loan_out", "loan_in", "acquisition", "conservation", "object_entry", "deaccession"}


def _validate_schema_target_type(target_type: str) -> None:
    if target_type not in SCHEMA_TARGET_TYPES:
        raise HTTPException(status_code=422, detail="Ungültiger Primärtyp.")


async def _ensure_schema_subtype_exists(db: DBDep, target_type: str, subtype: str | None) -> None:
    if target_type == "procedure":
        if subtype is not None and subtype not in PROCEDURE_TYPES:
            raise HTTPException(status_code=422, detail=f"Ungültiger Vorgangstyp '{subtype}'.")
        return
    await ensure_subtype_exists(db, target_type, subtype)


def _fd_read(f: FieldDefinition, children: list[FieldDefinitionRead] | None = None) -> FieldDefinitionRead:
    """Validate a FieldDefinition ORM object into FieldDefinitionRead without triggering lazy loads."""
    cols = {attr.key: getattr(f, attr.key) for attr in sa_inspect(type(f)).mapper.column_attrs}
    cols["children"] = children or []
    return FieldDefinitionRead.model_validate(cols)

router = APIRouter(prefix="/schema", tags=["schema"])


def _enqueue_reindex(target_type: str) -> None:
    """Fire-and-forget: enqueue a type-specific ES reindex after schema changes."""
    try:
        from katalon.workers.index_tasks import bulk_reindex_type_task
        bulk_reindex_type_task.delay(target_type)
    except Exception:
        pass  # ES / Celery may not be available in all environments


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


@router.get("/{target_type}", response_model=list[FieldDefinitionRead])
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


@router.post("", response_model=FieldDefinitionRead, status_code=201, dependencies=[require_role("admin")])
async def create_field(data: FieldDefinitionCreate, db: DBDep) -> FieldDefinitionRead:
    if not data.name or not data.name.strip():
        raise HTTPException(status_code=422, detail="Feldname darf nicht leer sein")
    _validate_schema_target_type(data.target_type)
    if data.parent_id:
        await _validate_parent(db, data.parent_id, data.field_type)
    else:
        await _ensure_schema_subtype_exists(db, data.target_type, data.target_subtype)
    field = FieldDefinition(**data.model_dump())
    db.add(field)
    await db.flush()
    _enqueue_reindex(data.target_type)
    return _fd_read(field)


@router.put("/{field_id}", response_model=FieldDefinitionRead, dependencies=[require_role("admin")])
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
    result = await db.execute(
        select(FieldDefinition).where(
            FieldDefinition.id == field_id, FieldDefinition.is_deleted.is_(False)
        )
    )
    field = result.scalar_one_or_none()
    if not field:
        raise HTTPException(status_code=404, detail="Felddefinition nicht gefunden")
    old_is_facet = field.is_facet
    for k, v in data.model_dump().items():
        setattr(field, k, v)
    await db.flush()
    if field.is_facet != old_is_facet:
        _enqueue_reindex(field.target_type)
    return _fd_read(field)


@router.delete("/{field_id}", status_code=204, dependencies=[require_role("admin")])
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


@router.post("/{field_id}/restore", response_model=FieldDefinitionRead, dependencies=[require_role("admin")])
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


@router.post("/import", response_model=ImportResult, status_code=200, dependencies=[require_role("admin")])
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
    existing_map: dict[str, FieldDefinition] = {
        f.name: f for f in existing_result.scalars().all()
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
        await ensure_subtype_exists(db, target_type, field_data.target_subtype)

        if name in existing_map:
            existing = existing_map[name]
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
