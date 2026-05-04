import json
import uuid

import yaml
from fastapi import APIRouter, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import or_, select

from katalon.core.dependencies import CurrentUser, DBDep, require_role
from katalon.core.models import FieldDefinition
from katalon.core.schemas import FieldDefinitionCreate, FieldDefinitionRead

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


@router.get("/{target_type}", response_model=list[FieldDefinitionRead])
async def list_fields(
    target_type: str,
    db: DBDep,
    subtype: str | None = Query(default=None, description="Filter to generic + this subtype"),
    include_deleted: bool = Query(False, description="Include soft-deleted fields"),
) -> list[FieldDefinition]:
    q = select(FieldDefinition).where(FieldDefinition.target_type == target_type)
    if subtype:
        q = q.where(
            or_(FieldDefinition.target_subtype.is_(None), FieldDefinition.target_subtype == subtype)
        )
    if not include_deleted:
        q = q.where(FieldDefinition.is_deleted.is_(False))
    result = await db.execute(q.order_by(FieldDefinition.sort_order))
    return list(result.scalars().all())


@router.post("", response_model=FieldDefinitionRead, status_code=201, dependencies=[require_role("admin")])
async def create_field(data: FieldDefinitionCreate, db: DBDep) -> FieldDefinition:
    if not data.name or not data.name.strip():
        raise HTTPException(status_code=422, detail="Feldname darf nicht leer sein")
    field = FieldDefinition(**data.model_dump())
    db.add(field)
    await db.flush()
    _enqueue_reindex(data.target_type)
    return field


@router.put("/{field_id}", response_model=FieldDefinitionRead, dependencies=[require_role("admin")])
async def update_field(
    field_id: uuid.UUID, data: FieldDefinitionCreate, db: DBDep
) -> FieldDefinition:
    if not data.name or not data.name.strip():
        raise HTTPException(status_code=422, detail="Feldname darf nicht leer sein")
    result = await db.execute(
        select(FieldDefinition).where(
            FieldDefinition.id == field_id, FieldDefinition.is_deleted.is_(False)
        )
    )
    field = result.scalar_one_or_none()
    if not field:
        raise HTTPException(status_code=404, detail="Felddefinition nicht gefunden")
    for k, v in data.model_dump().items():
        setattr(field, k, v)
    await db.flush()
    _enqueue_reindex(field.target_type)
    return field


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
    field.is_deleted = True
    target_type = field.target_type
    await db.flush()
    _enqueue_reindex(target_type)


@router.post("/{field_id}/restore", response_model=FieldDefinitionRead, dependencies=[require_role("admin")])
async def restore_field(field_id: uuid.UUID, db: DBDep) -> FieldDefinition:
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
    return field


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
        fields=[FieldDefinitionRead.model_validate(f) for f in result_fields],
    )
