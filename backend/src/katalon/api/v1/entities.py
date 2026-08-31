import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy import Text, cast, func, select
from sqlalchemy.orm.attributes import flag_modified

from katalon.core.concurrency import check_version, flush_record, require_version
from katalon.core.dependencies import (
    DBDep,
    OptionalCurrentUser,
    has_record_permission,
    require_record_permission,
    require_role,
)
from katalon.core.list_query import SortBy, SortDir, apply_sort
from katalon.core.models import AdminConfig, Entity, RecordSnapshot, User
from katalon.core.schemas import (
    AuditLogRead,
    EntityCreate,
    EntityRead,
    SnapshotCreate,
    SnapshotRead,
)
from katalon.core.visibility import (
    PUBLIC_STATUSES,
    apply_public_visibility,
    ensure_publicly_visible,
)
from katalon.services import pid_service, search_service
from katalon.services.audit_service import delete_label_fields, diff_fields, log_change
from katalon.services.idno_service import (
    consume_next_idno,
    maybe_advance_counter,
    validate_idno_pattern,
)
from katalon.services.public_metadata_service import project_public_record
from katalon.services.publish_service import can_publish, publish_record
from katalon.services.relation_service import count_relations, sync_schema_relations
from katalon.services.schema_service import prepare_metadata, validate_metadata
from katalon.services.subtype_service import (
    ensure_subtype_exists,
    normalize_subtype_name,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/entities", tags=["entities"])
#: Statuses that make a record publicly visible and trigger PID auto-minting.
PUBLIC_SAVE_STATUSES = set(PUBLIC_STATUSES)


async def _visibility_user(db: DBDep, user: OptionalCurrentUser) -> User | None:
    return user if user and await has_record_permission(db, user, "entity", "read") else None


@router.get(
    "",
    response_model=dict[str, Any],
    summary="List entities with pagination, filters and search",
)
async def list_entities(
    db: DBDep,
    current_user: OptionalCurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    entity_type: str | None = None,
    status: str | None = None,
    q: str | None = None,
    sort_by: SortBy | None = None,
    sort_dir: SortDir = "desc",
) -> dict[str, Any]:
    query = select(Entity)
    if entity_type:
        query = query.where(Entity.entity_type == entity_type)
    if status:
        query = query.where(Entity.status == status)
    visibility_user = await _visibility_user(db, current_user)
    query = apply_public_visibility(query, Entity, visibility_user)
    if q:
        query = query.where(
            Entity.idno.icontains(q, autoescape=True)
            | cast(Entity.metadata_, Text).icontains(q, autoescape=True)
        )

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    query = apply_sort(query.offset((page - 1) * page_size).limit(page_size), Entity, sort_by, sort_dir)
    items = (await db.execute(query)).scalars().all()
    response_items = [EntityRead.model_validate(i) for i in items]
    if visibility_user is None:
        response_items = [
            await project_public_record(db, item, "entity", entity.entity_type)
            for item, entity in zip(response_items, items, strict=True)
        ]
    return {"total": total, "page": page, "page_size": page_size, "items": response_items}


@router.post(
    "",
    response_model=EntityRead,
    status_code=201,
    summary="Create a new entity",
    responses={
        422: {"description": "Metadata validation failed or ID-Nr. pattern mismatch"},
        400: {"description": "ID-Nr. already assigned"},
        403: {"description": "Insufficient permissions"},
    },
)
async def create_entity(data: EntityCreate, db: DBDep, current_user: User = require_record_permission("entity", "create")) -> Entity:
    cfg_result = await db.execute(select(AdminConfig).where(AdminConfig.key == "default"))
    cfg = cfg_result.scalar_one_or_none()
    schema = (cfg.idno_schemas or {}).get("entity") if cfg else None
    pattern = (cfg.idno_patterns or {}).get("entity") if cfg else None

    if not data.idno or not data.idno.strip():
        if schema:
            idno = await consume_next_idno(db, "entity", schema)
        elif data.status == "draft":
            idno = None
        else:
            raise HTTPException(status_code=422, detail="ID-Nr. ist ein Pflichtfeld.")
    else:
        idno = data.idno.strip()
        if pattern and not validate_idno_pattern(pattern, idno):
            raise HTTPException(status_code=422, detail=f"ID-Nr. entspricht nicht dem Muster: {pattern}")
        if schema:
            await maybe_advance_counter(db, "entity", schema, idno)

    entity_type = normalize_subtype_name(
        data.entity_type,
        allow_null=True,
    )
    await ensure_subtype_exists(db, "entity", entity_type)
    metadata = await prepare_metadata(
        db, "entity", data.metadata_, entity_type,
        can_edit_locked=current_user.role in {"admin", "superuser"},
    )
    errors = await validate_metadata(
        db, "entity", metadata, entity_type, skip_required=data.status == "draft"
    )
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    if idno is not None:
        existing = await db.execute(select(Entity).where(Entity.idno == idno))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="ID-Nr. bereits vergeben.")
    entity = Entity(idno=idno, entity_type=entity_type, status=data.status, metadata_=metadata)
    db.add(entity)
    await flush_record(db, entity)
    await sync_schema_relations(db, "entity", entity.id, metadata)
    await db.flush()
    await log_change(db, record_type="entity", record_id=entity.id, user_id=current_user.id, action="create")
    if data.status in PUBLIC_SAVE_STATUSES:
        try:
            await pid_service.ensure_pids_on_publish(db, "entity", entity, current_user.id)
        except pid_service.PidMintError as exc:
            raise HTTPException(status_code=422, detail=f"PID-Vergabe fehlgeschlagen: {exc}") from exc
    try:
        await search_service.index_record("entity", entity, db)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    return entity


@router.get(
    "/{entity_id}",
    response_model=EntityRead,
    summary="Get a single entity by ID",
    responses={
        404: {"description": "Entity not found"},
    },
)
async def get_entity(entity_id: uuid.UUID, db: DBDep, current_user: OptionalCurrentUser) -> Entity | EntityRead:
    result = await db.execute(select(Entity).where(Entity.id == entity_id))
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entität nicht gefunden")
    visibility_user = await _visibility_user(db, current_user)
    ensure_publicly_visible(entity, visibility_user, "Entität nicht gefunden")
    if visibility_user is None:
        return await project_public_record(db, EntityRead.model_validate(entity), "entity", entity.entity_type)
    return entity


@router.put(
    "/{entity_id}",
    response_model=EntityRead,
    summary="Update an entity",
    responses={
        404: {"description": "Entity not found"},
        400: {"description": "ID-Nr. already assigned"},
        422: {"description": "Metadata validation failed"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Version conflict (If-Match mismatch)"},
    },
)
async def update_entity(
    entity_id: uuid.UUID,
    data: EntityCreate,
    db: DBDep,
    current_user: User = require_record_permission("entity", "update"),
    if_match: int | None = Header(None, alias="If-Match"),
) -> Entity:
    result = await db.execute(select(Entity).where(Entity.id == entity_id))
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entität nicht gefunden")
    check_version(entity.version, if_match)
    if not data.idno or not data.idno.strip():
        if data.status == "draft":
            idno = None
        else:
            raise HTTPException(status_code=422, detail="ID-Nr. ist ein Pflichtfeld.")
    else:
        idno = data.idno.strip()
        existing = await db.execute(select(Entity).where(Entity.idno == idno, Entity.id != entity_id))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="ID-Nr. bereits vergeben.")
    entity_type = normalize_subtype_name(
        data.entity_type,
        allow_null=True,
    )
    await ensure_subtype_exists(db, "entity", entity_type)
    metadata = await prepare_metadata(
        db, "entity", data.metadata_, entity_type, existing=entity.metadata_,
        can_edit_locked=current_user.role in {"admin", "superuser"},
    )
    errors = await validate_metadata(
        db, "entity", metadata, entity_type, skip_required=data.status == "draft"
    )
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    old = {
        "idno": entity.idno,
        "entity_type": entity.entity_type,
        "status": entity.status,
        "metadata": entity.metadata_,
    }
    entity.idno = idno
    entity.entity_type = entity_type
    entity.status = data.status
    entity.metadata_ = metadata

    await flush_record(db, entity)
    await sync_schema_relations(db, "entity", entity.id, metadata)
    entity_diff = diff_fields(old, {"idno": idno, "entity_type": entity_type, "status": data.status, "metadata": metadata})
    if entity_diff:
        await log_change(db, record_type="entity", record_id=entity.id, user_id=current_user.id, action="update",
                         changed_fields=entity_diff)
    if (
        old["status"] not in PUBLIC_SAVE_STATUSES
        and data.status in PUBLIC_SAVE_STATUSES
    ):
        try:
            await pid_service.ensure_pids_on_publish(db, "entity", entity, current_user.id)
        except pid_service.PidMintError as exc:
            raise HTTPException(status_code=422, detail=f"PID-Vergabe fehlgeschlagen: {exc}") from exc
    try:
        await search_service.index_record("entity", entity, db)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    return entity


@router.post(
    "/{entity_id}/publish",
    summary="Publish an entity after validating required fields",
    responses={
        422: {"description": "Required fields missing or invalid"},
        403: {"description": "Insufficient permissions"},
    },
)
async def publish_entity(
    entity_id: uuid.UUID,
    db: DBDep,
    current_user: User = require_record_permission("entity", "update"),
) -> dict[str, Any]:
    """Publish an entity after validating required fields."""
    ok, errors = await can_publish(db, "entity", str(entity_id))
    if not ok:
        raise HTTPException(status_code=422, detail={"errors": errors})
    result = await publish_record(db, "entity", str(entity_id), str(current_user.id))
    if not result.get("ok"):
        raise HTTPException(status_code=422, detail={"errors": result.get("errors", [])})
    await db.commit()
    return result


@router.delete(
    "/{entity_id}",
    status_code=204,
    summary="Delete an entity",
    responses={
        404: {"description": "Entity not found"},
        409: {"description": "Entity has related records (use force=true to override)"},
        403: {"description": "Insufficient permissions"},
    },
)
async def delete_entity(
    entity_id: uuid.UUID,
    db: DBDep,
    current_user: User = require_record_permission("entity", "delete"),
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

    entity.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    await log_change(
        db, record_type="entity", record_id=entity.id, user_id=current_user.id, action="delete",
        changed_fields=delete_label_fields(entity.idno, entity.metadata_),
    )
    await flush_record(db, entity)
    try:
        await search_service.remove_record(entity.id)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)

    from katalon.workers.cleanup_tasks import cleanup_relation_refs
    from katalon.workers.enqueue import enqueue
    enqueue(cleanup_relation_refs, "entity", str(entity_id))


@router.post(
    "/{entity_id}/restore",
    response_model=EntityRead,
    summary="Restore a soft-deleted entity",
    responses={
        404: {"description": "Entity not found or not deleted"},
        403: {"description": "Insufficient permissions"},
    },
)
async def restore_entity(
    entity_id: uuid.UUID,
    db: DBDep,
    current_user: User = require_role("admin"),
) -> Entity:
    result = await db.execute(select(Entity).where(Entity.id == entity_id))
    entity = result.scalar_one_or_none()
    if not entity or entity.deleted_at is None:
        raise HTTPException(status_code=404, detail="Entität nicht gefunden")
    entity.deleted_at = None
    await log_change(db, record_type="entity", record_id=entity.id, user_id=current_user.id, action="undelete")
    await flush_record(db, entity)
    try:
        await search_service.index_record("entity", entity, db)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    return entity


@router.get(
    "/trash/list",
    response_model=list[EntityRead],
    summary="List soft-deleted entities",
)
async def list_deleted_entities(db: DBDep, current_user: User = require_role("admin")) -> list[Entity]:
    result = await db.execute(
        select(Entity).where(Entity.deleted_at.is_not(None)).order_by(Entity.deleted_at.desc())
    )
    return list(result.scalars().all())


@router.post(
    "/{entity_id}/snapshots",
    response_model=SnapshotRead,
    status_code=201,
    summary="Create a snapshot of an entity's current state",
    responses={
        404: {"description": "Entity not found"},
        403: {"description": "Insufficient permissions"},
    },
)
async def create_snapshot(
    entity_id: uuid.UUID, data: SnapshotCreate, db: DBDep, current_user: User = require_record_permission("entity", "update")
) -> RecordSnapshot:
    result = await db.execute(select(Entity).where(Entity.id == entity_id))
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entität nicht gefunden")
    snap = RecordSnapshot(
        record_type="entity",
        record_id=entity.id,
        label=data.label,
        snapshot={
            "idno": entity.idno,
            "entity_type": entity.entity_type,
            "status": entity.status,
            "metadata": entity.metadata_,
        },
        created_by=current_user.id,
    )
    db.add(snap)
    await db.flush()
    return snap


@router.get(
    "/{entity_id}/snapshots",
    response_model=list[SnapshotRead],
    summary="List snapshots for an entity",
)
async def list_snapshots(entity_id: uuid.UUID, db: DBDep) -> list[RecordSnapshot]:
    result = await db.execute(
        select(RecordSnapshot)
        .where(RecordSnapshot.record_type == "entity", RecordSnapshot.record_id == entity_id)
        .order_by(RecordSnapshot.created_at.desc())
    )
    return list(result.scalars().all())


@router.post(
    "/{entity_id}/snapshots/{snapshot_id}/restore",
    response_model=EntityRead,
    summary="Restore an entity from a snapshot",
    responses={
        404: {"description": "Snapshot or entity not found"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Version conflict"},
        428: {"description": "If-Match header required"},
    },
)
async def restore_snapshot(
    entity_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    db: DBDep,
    current_user: User = require_record_permission("entity", "update"),
    if_match: int | None = Header(None, alias="If-Match"),
) -> Entity:
    snap_result = await db.execute(
        select(RecordSnapshot).where(
            RecordSnapshot.id == snapshot_id,
            RecordSnapshot.record_type == "entity",
            RecordSnapshot.record_id == entity_id,
        )
    )
    snap = snap_result.scalar_one_or_none()
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot nicht gefunden")

    entity_result = await db.execute(select(Entity).where(Entity.id == entity_id))
    entity = entity_result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entität nicht gefunden")
    require_version(entity.version, if_match)

    data = snap.snapshot
    if "idno" in data:
        entity.idno = data["idno"]
    if "entity_type" in data:
        entity.entity_type = data["entity_type"]
    if "status" in data:
        entity.status = data["status"]
    if "metadata" in data:
        entity.metadata_ = data["metadata"]
    flag_modified(entity, "metadata_")
    await flush_record(db, entity)
    await sync_schema_relations(db, "entity", entity.id, entity.metadata_)
    await log_change(
        db,
        record_type="entity",
        record_id=entity.id,
        user_id=current_user.id,
        action="restore",
        changed_fields={"snapshot_id": str(snapshot_id)},
    )
    await db.commit()
    try:
        await search_service.index_record("entity", entity, db)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    return entity


@router.get(
    "/{entity_id}/audit-log",
    response_model=list[AuditLogRead],
    summary="List audit log entries for an entity",
)
async def list_entity_audit_log(entity_id: uuid.UUID, db: DBDep) -> list[AuditLogRead]:
    from katalon.api.v1.audit import list_audit_log
    return await list_audit_log(db, record_type="entity", record_id=entity_id, limit=100)
