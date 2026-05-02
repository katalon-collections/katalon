import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import or_, select

from katalon.core.dependencies import CurrentUser, DBDep
from katalon.core.models import FieldDefinition
from katalon.core.schemas import FieldDefinitionCreate, FieldDefinitionRead

router = APIRouter(prefix="/schema", tags=["schema"])


@router.get("/{target_type}", response_model=list[FieldDefinitionRead])
async def list_fields(
    target_type: str,
    db: DBDep,
    subtype: str | None = Query(default=None, description="Filter to generic + this subtype"),
) -> list[FieldDefinition]:
    q = select(FieldDefinition).where(FieldDefinition.target_type == target_type)
    if subtype:
        q = q.where(
            or_(FieldDefinition.target_subtype.is_(None), FieldDefinition.target_subtype == subtype)
        )
    result = await db.execute(q.order_by(FieldDefinition.sort_order))
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
    result = await db.execute(select(FieldDefinition).where(FieldDefinition.id == field_id))
    field = result.scalar_one_or_none()
    if not field:
        raise HTTPException(status_code=404, detail="Felddefinition nicht gefunden")
    for k, v in data.model_dump().items():
        setattr(field, k, v)
    return field


@router.delete("/{field_id}", status_code=204)
async def delete_field(field_id: uuid.UUID, db: DBDep, _: CurrentUser) -> None:
    result = await db.execute(select(FieldDefinition).where(FieldDefinition.id == field_id))
    field = result.scalar_one_or_none()
    if not field:
        raise HTTPException(status_code=404, detail="Felddefinition nicht gefunden")
    await db.delete(field)
