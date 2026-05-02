import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from katalon.core.dependencies import CurrentUser, DBDep
from katalon.core.models import FieldDefinition
from katalon.core.schemas import FieldDefinitionCreate, FieldDefinitionRead

router = APIRouter(prefix="/schema", tags=["schema"])


@router.get("/{target_type}", response_model=list[FieldDefinitionRead])
async def list_fields(
    target_type: str,
    db: DBDep,
    include_deleted: bool = Query(False, description="Include soft-deleted fields"),
) -> list[FieldDefinition]:
    q = select(FieldDefinition).where(FieldDefinition.target_type == target_type)
    if not include_deleted:
        q = q.where(FieldDefinition.is_deleted.is_(False))
    q = q.order_by(FieldDefinition.sort_order)
    result = await db.execute(q)
    return list(result.scalars().all())


@router.post("", response_model=FieldDefinitionRead, status_code=201)
async def create_field(data: FieldDefinitionCreate, db: DBDep, _: CurrentUser) -> FieldDefinition:
    if not data.name or not data.name.strip():
        raise HTTPException(status_code=422, detail="Feldname darf nicht leer sein")
    field = FieldDefinition(**data.model_dump())
    db.add(field)
    await db.flush()
    return field


@router.put("/{field_id}", response_model=FieldDefinitionRead)
async def update_field(
    field_id: uuid.UUID, data: FieldDefinitionCreate, db: DBDep, _: CurrentUser
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
    return field


@router.delete("/{field_id}", status_code=204)
async def delete_field(field_id: uuid.UUID, db: DBDep, _: CurrentUser) -> None:
    result = await db.execute(
        select(FieldDefinition).where(
            FieldDefinition.id == field_id, FieldDefinition.is_deleted.is_(False)
        )
    )
    field = result.scalar_one_or_none()
    if not field:
        raise HTTPException(status_code=404, detail="Felddefinition nicht gefunden")
    field.is_deleted = True


@router.post("/{field_id}/restore", response_model=FieldDefinitionRead)
async def restore_field(field_id: uuid.UUID, db: DBDep, _: CurrentUser) -> FieldDefinition:
    """Restore a soft-deleted field definition."""
    result = await db.execute(
        select(FieldDefinition).where(
            FieldDefinition.id == field_id, FieldDefinition.is_deleted.is_(True)
        )
    )
    field = result.scalar_one_or_none()
    if not field:
        raise HTTPException(status_code=404, detail="Gelöschte Felddefinition nicht gefunden")
    field.is_deleted = False
    return field
