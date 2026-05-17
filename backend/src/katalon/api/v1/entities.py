import logging
import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

logger = logging.getLogger(__name__)

from katalon.core.dependencies import CurrentUser, DBDep
from katalon.core.models import AdminConfig, Entity, RecordSnapshot
from katalon.core.schemas import (
    AuditLogRead,
    EntityCreate,
    EntityRead,
    SnapshotCreate,
    SnapshotRead,
)
from katalon.services import search_service
from katalon.services.audit_service import log_change
from katalon.services.idno_service import consume_next_idno, maybe_advance_counter, validate_idno_pattern
from katalon.services.relation_service import count_relations, delete_relations, sync_schema_relations
from katalon.services.schema_service import validate_metadata
from katalon.services.subtype_service import ensure_subtype_exists, has_any_subtypes, normalize_subtype_name

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
    cfg_result = await db.execute(select(AdminConfig).where(AdminConfig.key == "default"))
    cfg = cfg_result.scalar_one_or_none()
    schema = (cfg.idno_schemas or {}).get("entity") if cfg else None
    pattern = (cfg.idno_patterns or {}).get("entity") if cfg else None

    if not data.idno or not data.idno.strip():
        if schema:
            idno = await consume_next_idno(db, "entity", schema)
        else:
            raise HTTPException(status_code=422, detail="ID-Nr. ist ein Pflichtfeld.")
    else:
        idno = data.idno.strip()
        if pattern and not validate_idno_pattern(pattern, idno):
            raise HTTPException(status_code=422, detail=f"ID-Nr. entspricht nicht dem Muster: {pattern}")
        if schema:
            await maybe_advance_counter(db, "entity", schema, idno)

    _has_subtypes = await has_any_subtypes(db, "entity")
    entity_type = normalize_subtype_name(data.entity_type, allow_null=not _has_subtypes)
    await ensure_subtype_exists(db, "entity", entity_type)
    errors = await validate_metadata(db, "entity", data.metadata_, entity_type)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    existing = await db.execute(select(Entity).where(Entity.idno == idno))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="ID-Nr. bereits vergeben.")
    entity = Entity(idno=idno, entity_type=entity_type, status=data.status, metadata_=data.metadata_)
    db.add(entity)
    await db.flush()
    await sync_schema_relations(db, "entity", entity.id, data.metadata_)
    await db.flush()
    await log_change(db, record_type="entity", record_id=entity.id, user_id=current_user.id, action="create")
    try:
        await search_service.index_record("entity", entity)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
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
    if not data.idno or not data.idno.strip():
        raise HTTPException(status_code=422, detail="ID-Nr. ist ein Pflichtfeld.")
    result = await db.execute(select(Entity).where(Entity.id == entity_id))
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entität nicht gefunden")
    existing = await db.execute(select(Entity).where(Entity.idno == data.idno.strip(), Entity.id != entity_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="ID-Nr. bereits vergeben.")
    entity_type = normalize_subtype_name(data.entity_type, allow_null=False)
    await ensure_subtype_exists(db, "entity", entity_type)
    errors = await validate_metadata(db, "entity", data.metadata_, entity_type)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    old = {
        "idno": entity.idno,
        "entity_type": entity.entity_type,
        "status": entity.status,
        "metadata": entity.metadata_,
    }
    entity.idno = data.idno.strip()
    entity.entity_type = entity_type
    entity.status = data.status
    entity.metadata_ = data.metadata_
    await sync_schema_relations(db, "entity", entity.id, data.metadata_)
    await log_change(db, record_type="entity", record_id=entity.id, user_id=current_user.id, action="update",
                     changed_fields={"old": old, "new": {"idno": data.idno, "entity_type": entity_type, "status": data.status, "metadata": data.metadata_}})
    try:
        await search_service.index_record("entity", entity)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    return entity


@router.delete("/{entity_id}", status_code=204)
async def delete_entity(
    entity_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentUser,
    force: bool = Query(False),
) -> None:
    result = await db.execute(select(Entity).where(Entity.id == entity_id))
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entität nicht gefunden")

    related_count = await count_relations(db, "entity", entity_id)
    if related_count > 0 and not force:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": f"Dieser Datensatz ist mit {related_count} anderen Datensätzen verknüpft.",
                "related_count": related_count,
            },
        )

    if related_count > 0:
        await delete_relations(db, "entity", entity_id)

    await log_change(db, record_type="entity", record_id=entity.id, user_id=current_user.id, action="delete")
    try:
        await search_service.remove_record(entity.id)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    await db.delete(entity)

    from katalon.workers.cleanup_tasks import cleanup_relation_refs
    cleanup_relation_refs.delay("entity", str(entity_id))


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


@router.get("/{entity_id}/audit-log", response_model=list[AuditLogRead])
async def list_entity_audit_log(entity_id: uuid.UUID, db: DBDep) -> list[AuditLogRead]:
    from katalon.api.v1.audit import list_audit_log
    return await list_audit_log(db, record_type="entity", record_id=entity_id, limit=100)
