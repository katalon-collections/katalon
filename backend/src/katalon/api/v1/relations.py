import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from katalon.core.dependencies import DBDep, require_admin_or_editor
from katalon.core.models import Relation
from katalon.core.schemas import RelationCreate, RelationRead, RelationUpdate

router = APIRouter(prefix="/relations", tags=["relations"])


@router.get("", response_model=list[RelationRead])
async def list_relations(
    db: DBDep,
    from_type: str | None = None,
    from_id: uuid.UUID | None = None,
    to_type: str | None = None,
    to_id: uuid.UUID | None = None,
    limit: int = Query(100, ge=1, le=500),
) -> list[Relation]:
    query = select(Relation).limit(limit).order_by(Relation.created_at.desc())
    if from_type:
        query = query.where(Relation.from_type == from_type)
    if from_id:
        query = query.where(Relation.from_id == from_id)
    if to_type:
        query = query.where(Relation.to_type == to_type)
    if to_id:
        query = query.where(Relation.to_id == to_id)
    return list((await db.execute(query)).scalars().all())


@router.post("", response_model=RelationRead, status_code=201)
async def create_relation(data: RelationCreate, db: DBDep, current_user=require_admin_or_editor()) -> Relation:
    rel = Relation(
        from_type=data.from_type, from_id=data.from_id,
        to_type=data.to_type, to_id=data.to_id,
        relation_type=data.relation_type, metadata_=data.metadata_,
    )
    db.add(rel)
    await db.flush()
    return rel


@router.put("/{relation_id}", response_model=RelationRead)
async def update_relation(
    relation_id: uuid.UUID, data: RelationUpdate, db: DBDep, current_user=require_admin_or_editor()
) -> Relation:
    result = await db.execute(select(Relation).where(Relation.id == relation_id))
    rel = result.scalar_one_or_none()
    if not rel:
        raise HTTPException(status_code=404, detail="Relation nicht gefunden")
    if data.relation_type is not None:
        rel.relation_type = data.relation_type
    if data.metadata_ is not None:
        rel.metadata_ = data.metadata_
    await db.flush()
    return rel


@router.delete("/{relation_id}", status_code=204)
async def delete_relation(relation_id: uuid.UUID, db: DBDep, current_user=require_admin_or_editor()) -> None:
    result = await db.execute(select(Relation).where(Relation.id == relation_id))
    rel = result.scalar_one_or_none()
    if not rel:
        raise HTTPException(status_code=404, detail="Relation nicht gefunden")
    await db.delete(rel)
