import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from katalon.core.dependencies import DBDep, require_admin_or_editor, require_role
from katalon.core.models import RecordSubtype
from katalon.core.schemas import RecordSubtypeCreate, RecordSubtypeRead
from katalon.services.subtype_service import (
    normalize_subtype_name,
    retire_subtype_configuration,
    subtype_has_assigned_records,
    validate_primary_type,
)

router = APIRouter(prefix="/record-subtypes", tags=["record-subtypes"])


async def _unset_default_for_type(db: DBDep, primary_type: str, *, keep_id: uuid.UUID | None) -> None:
    result = await db.execute(
        select(RecordSubtype).where(
            RecordSubtype.primary_type == primary_type,
            RecordSubtype.is_default.is_(True),
        )
    )
    for subtype in result.scalars().all():
        if keep_id is None or subtype.id != keep_id:
            subtype.is_default = False


@router.get(
    "",
    response_model=list[RecordSubtypeRead],
    dependencies=[require_admin_or_editor()],
    summary="List record subtypes, optionally filtered by primary type",
    responses={
        403: {"description": "Insufficient permissions"},
        422: {"description": "Invalid primary type"},
    },
)
async def list_record_subtypes(db: DBDep, primary_type: str | None = Query(default=None)) -> list[RecordSubtype]:
    q = select(RecordSubtype)
    if primary_type is not None:
        validate_primary_type(primary_type)
        q = q.where(RecordSubtype.primary_type == primary_type)
    result = await db.execute(q.order_by(RecordSubtype.primary_type, RecordSubtype.sort_order, RecordSubtype.name))
    return list(result.scalars().all())


@router.post(
    "",
    response_model=RecordSubtypeRead,
    status_code=201,
    dependencies=[require_role("admin")],
    summary="Create a new record subtype",
    responses={
        400: {"description": "Subtype already exists"},
        403: {"description": "Insufficient permissions"},
        422: {"description": "Invalid primary type or subtype name"},
    },
)
async def create_record_subtype(data: RecordSubtypeCreate, db: DBDep) -> RecordSubtype:
    validate_primary_type(data.primary_type)
    name = normalize_subtype_name(data.name, allow_null=False)

    existing_result = await db.execute(
        select(RecordSubtype).where(
            RecordSubtype.primary_type == data.primary_type,
            RecordSubtype.name == name,
        )
    )
    if existing_result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="Subtyp existiert bereits.")

    subtype = RecordSubtype(
        primary_type=data.primary_type,
        name=name,
        label=data.label,
        description=data.description,
        sort_order=data.sort_order,
        is_default=data.is_default,
    )
    if subtype.is_default:
        await _unset_default_for_type(db, subtype.primary_type, keep_id=None)
    db.add(subtype)
    await db.flush()
    return subtype


@router.put(
    "/{subtype_id}",
    response_model=RecordSubtypeRead,
    dependencies=[require_role("admin")],
    summary="Update a record subtype",
    responses={
        400: {"description": "Subtype already exists"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Subtype not found"},
        422: {"description": "Invalid primary type or subtype name"},
    },
)
async def update_record_subtype(
    subtype_id: uuid.UUID, data: RecordSubtypeCreate, db: DBDep
) -> RecordSubtype:
    validate_primary_type(data.primary_type)
    name = normalize_subtype_name(data.name, allow_null=False)
    assert name is not None  # allow_null=False raises HTTPException instead of returning None

    result = await db.execute(select(RecordSubtype).where(RecordSubtype.id == subtype_id))
    subtype = result.scalar_one_or_none()
    if subtype is None:
        raise HTTPException(status_code=404, detail="Subtyp nicht gefunden.")
    existing_result = await db.execute(
        select(RecordSubtype).where(
            RecordSubtype.primary_type == data.primary_type,
            RecordSubtype.name == name,
            RecordSubtype.id != subtype_id,
        )
    )
    if existing_result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="Subtyp existiert bereits.")

    if data.is_default:
        await _unset_default_for_type(db, data.primary_type, keep_id=subtype_id)

    subtype.primary_type = data.primary_type
    subtype.name = name
    subtype.label = data.label
    subtype.description = data.description
    subtype.sort_order = data.sort_order
    subtype.is_default = data.is_default
    await db.flush()
    return subtype


@router.delete(
    "/{subtype_id}",
    status_code=204,
    dependencies=[require_role("admin")],
    summary="Delete a record subtype",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Subtype not found"},
        409: {"description": "Subtype still in use by existing records"},
    },
)
async def delete_record_subtype(subtype_id: uuid.UUID, db: DBDep) -> None:
    result = await db.execute(select(RecordSubtype).where(RecordSubtype.id == subtype_id))
    subtype = result.scalar_one_or_none()
    if subtype is None:
        raise HTTPException(status_code=404, detail="Subtyp nicht gefunden.")
    if await subtype_has_assigned_records(db, subtype.primary_type, subtype.name):
        raise HTTPException(
            status_code=409,
            detail="Subtyp ist noch in Benutzung und kann nicht gelöscht werden.",
        )

    await retire_subtype_configuration(db, subtype.primary_type, subtype.name)
    await db.delete(subtype)
