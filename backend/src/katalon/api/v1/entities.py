import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.dependencies import CurrentUser, DBDep
from katalon.core.models import Entity, RecordSnapshot
from katalon.core.schemas import EntityCreate, EntityRead, SnapshotCreate, SnapshotRead
from katalon.services.audit_service import log_change
from katalon.services.schema_service import validate_metadata
from katalon.services import search_service

router = APIRouter(prefix="/entities", tags=["entities"])


@router.get("", response_model=dict)
async def list_entities(
    db: DBDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    entity_type: str | None = None,
    status: str | None = None,
    q: str | None = None,
) -> dict:
    query = select(Entity)
    if entity_type:
        query = query.where(Entity.entity_type == entity_type)
    if status:
        query = query.where(Entity.status == status)
    if q:
        query = query.where(Entity.search_vector.match(q))

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    query = query.offset((page - 1) * page_size).limit(page_size).order_by(Entity.updated_at.desc())
    items = (await db.execute(query)).scalars().all()
    return {"total": total, "page": page, "page_size": page_size, "items": [EntityRead.model_validate(i) for i in items]}


@router.post("", response_model=EntityRead, status_code=201)
async def create_entity(data: EntityCreate, db: DBDep, current_user: CurrentUser) -> Entity:
    errors = await validate_metadata(db, "entity", data.metadata_, data.entity_type or None)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    entity = Entity(entity_type=data.entity_type, status=data.status, metadata_=data.metadata_)
    db.add(entity)
    await db.flush()
    await log_change(db, record_type="entity", record_id=entity.id, user_id=current_user.id, action="create")
    try:
        await search_service.index_record("entity", entity)
    except Exception:
        pass
    return entity


@router.get("/{entity_id}", response_model=EntityRead)
async def get_entity(entity_id: uuid.UUID, db: DBDep) -> Entity:
    result = await db.execute(select(Entity).where(Entity.id == entity_id))
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entität nicht gefunden")
    return entity


@router.put("/{entity_id}", response_model=EntityRead)
async def update_entity(entity_id: uuid.UUID, data: EntityCreate, db: DBDep, current_user: CurrentUser) -> Entity:
    result = await db.execute(select(Entity).where(Entity.id == entity_id))
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entität nicht gefunden")
    errors = await validate_metadata(db, "entity", data.metadata_, data.entity_type or None)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    old = {"status": entity.status, "metadata": entity.metadata_}
    entity.entity_type = data.entity_type
    entity.status = data.status
    entity.metadata_ = data.metadata_
    await log_change(db, record_type="entity", record_id=entity.id, user_id=current_user.id, action="update",
                     changed_fields={"old": old, "new": {"status": data.status, "metadata": data.metadata_}})
    try:
        await search_service.index_record("entity", entity)
    except Exception:
        pass
    return entity


@router.delete("/{entity_id}", status_code=204)
async def delete_entity(entity_id: uuid.UUID, db: DBDep, current_user: CurrentUser) -> None:
    result = await db.execute(select(Entity).where(Entity.id == entity_id))
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entität nicht gefunden")
    await log_change(db, record_type="entity", record_id=entity.id, user_id=current_user.id, action="delete")
    try:
        await search_service.remove_record(entity.id)
    except Exception:
        pass
    await db.delete(entity)


@router.post("/{entity_id}/snapshots", response_model=SnapshotRead, status_code=201)
async def create_snapshot(entity_id: uuid.UUID, data: SnapshotCreate, db: DBDep, current_user: CurrentUser) -> RecordSnapshot:
    result = await db.execute(select(Entity).where(Entity.id == entity_id))
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entität nicht gefunden")
    snap = RecordSnapshot(record_type="entity", record_id=entity.id, label=data.label,
                          snapshot={"entity_type": entity.entity_type, "status": entity.status, "metadata": entity.metadata_},
                          created_by=current_user.id)
    db.add(snap)
    await db.flush()
    return snap
