import logging
import uuid

from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm.attributes import flag_modified

from katalon.core.concurrency import check_version, flush_record, require_version
from katalon.core.dependencies import (
    DBDep,
    OptionalCurrentUser,
    has_record_permission,
    require_record_permission,
)
from katalon.core.models import AdminConfig, Place, RecordSnapshot
from katalon.core.schemas import AuditLogRead, PlaceCreate, PlaceRead, SnapshotCreate, SnapshotRead
from katalon.core.visibility import apply_public_visibility, ensure_publicly_visible
from katalon.services import search_service
from katalon.services.audit_service import log_change
from katalon.services.idno_service import (
    consume_next_idno,
    maybe_advance_counter,
    validate_idno_pattern,
)
from katalon.services.publish_service import can_publish, publish_record
from katalon.services.relation_service import (
    count_relations,
    delete_relations,
    sync_schema_relations,
)
from katalon.services.schema_service import prepare_metadata, validate_metadata
from katalon.services.subtype_service import (
    ensure_subtype_exists,
    has_any_subtypes,
    normalize_subtype_name,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/places", tags=["places"])


async def _visibility_user(db: DBDep, user: OptionalCurrentUser):
    return user if user and await has_record_permission(db, user, "place", "read") else None


@router.get(
    "",
    response_model=dict,
    summary="List places with pagination and filters",
)
async def list_places(
    db: DBDep,
    current_user: OptionalCurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    place_type: str | None = None,
    status: str | None = None,
    q: str | None = None,
) -> dict:
    query = select(Place)
    if place_type:
        query = query.where(Place.place_type == place_type)
    if status:
        query = query.where(Place.status == status)
    query = apply_public_visibility(query, Place, await _visibility_user(db, current_user))
    if q:
        query = query.where(Place.search_vector.match(q))
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    query = query.offset((page - 1) * page_size).limit(page_size).order_by(Place.updated_at.desc())
    items = (await db.execute(query)).scalars().all()
    return {"total": total, "page": page, "page_size": page_size, "items": [PlaceRead.model_validate(i) for i in items]}


@router.post(
    "",
    response_model=PlaceRead,
    status_code=201,
    summary="Create a new place record",
    responses={
        403: {"description": "Insufficient permissions"},
        400: {"description": "Idno already taken"},
        422: {"description": "Idno missing/invalid pattern or metadata validation failed"},
    },
)
async def create_place(data: PlaceCreate, db: DBDep, current_user=require_record_permission("place", "create")) -> Place:
    cfg_result = await db.execute(select(AdminConfig).where(AdminConfig.key == "default"))
    cfg = cfg_result.scalar_one_or_none()
    schema = (cfg.idno_schemas or {}).get("place") if cfg else None
    pattern = (cfg.idno_patterns or {}).get("place") if cfg else None

    if not data.idno or not data.idno.strip():
        if schema:
            idno = await consume_next_idno(db, "place", schema)
        elif data.status == "draft":
            idno = None
        else:
            raise HTTPException(status_code=422, detail="ID-Nr. ist ein Pflichtfeld.")
    else:
        idno = data.idno.strip()
        if pattern and not validate_idno_pattern(pattern, idno):
            raise HTTPException(status_code=422, detail=f"ID-Nr. entspricht nicht dem Muster: {pattern}")
        if schema:
            await maybe_advance_counter(db, "place", schema, idno)

    _has_subtypes = await has_any_subtypes(db, "place")
    place_type = normalize_subtype_name(
        data.place_type,
        allow_null=data.status == "draft" or not _has_subtypes,
    )
    await ensure_subtype_exists(db, "place", place_type)
    metadata = await prepare_metadata(
        db, "place", data.metadata_, place_type,
        can_edit_locked=current_user.role in {"admin", "superuser"},
    )
    errors = await validate_metadata(
        db, "place", metadata, place_type, skip_required=data.status == "draft"
    )
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    if idno is not None:
        existing = await db.execute(select(Place).where(Place.idno == idno))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="ID-Nr. bereits vergeben.")
    place = Place(
        idno=idno,
        place_type=place_type,
        status=data.status,
        metadata_=metadata,
    )
    if data.lat is not None and data.lon is not None:
        from geoalchemy2.elements import WKTElement
        place.geom = WKTElement(f"POINT({data.lon} {data.lat})", srid=4326)
    db.add(place)
    await flush_record(db, place)
    await sync_schema_relations(db, "place", place.id, metadata)
    await db.flush()
    await log_change(db, record_type="place", record_id=place.id, user_id=current_user.id, action="create")
    try:
        await search_service.index_record("place", place, db)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    return place


@router.get(
    "/{place_id}",
    response_model=PlaceRead,
    summary="Get a single place by ID",
    responses={
        404: {"description": "Place not found"},
    },
)
async def get_place(place_id: uuid.UUID, db: DBDep, current_user: OptionalCurrentUser) -> Place:
    result = await db.execute(select(Place).where(Place.id == place_id))
    place = result.scalar_one_or_none()
    if not place:
        raise HTTPException(status_code=404, detail="Ort nicht gefunden")
    ensure_publicly_visible(place, await _visibility_user(db, current_user), "Ort nicht gefunden")
    return place


@router.put(
    "/{place_id}",
    response_model=PlaceRead,
    summary="Update a place record",
    responses={
        404: {"description": "Place not found"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Version conflict (If-Match mismatch)"},
        400: {"description": "Idno already taken"},
        422: {"description": "Idno missing or metadata validation failed"},
    },
)
async def update_place(
    place_id: uuid.UUID,
    data: PlaceCreate,
    db: DBDep,
    current_user=require_record_permission("place", "update"),
    if_match: int | None = Header(None, alias="If-Match"),
) -> Place:
    result = await db.execute(select(Place).where(Place.id == place_id))
    place = result.scalar_one_or_none()
    if not place:
        raise HTTPException(status_code=404, detail="Ort nicht gefunden")
    check_version(place.version, if_match)
    if not data.idno or not data.idno.strip():
        if data.status == "draft":
            idno = None
        else:
            raise HTTPException(status_code=422, detail="ID-Nr. ist ein Pflichtfeld.")
    else:
        idno = data.idno.strip()
        existing = await db.execute(select(Place).where(Place.idno == idno, Place.id != place_id))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="ID-Nr. bereits vergeben.")
    _has_subtypes = await has_any_subtypes(db, "place")
    place_type = normalize_subtype_name(
        data.place_type,
        allow_null=data.status == "draft" or not _has_subtypes,
    )
    await ensure_subtype_exists(db, "place", place_type)
    metadata = await prepare_metadata(
        db, "place", data.metadata_, place_type, existing=place.metadata_,
        can_edit_locked=current_user.role in {"admin", "superuser"},
    )
    errors = await validate_metadata(
        db, "place", metadata, place_type, skip_required=data.status == "draft"
    )
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    old = {
        "idno": place.idno,
        "place_type": place.place_type,
        "status": place.status,
        "metadata": place.metadata_,
    }
    place.idno = idno
    place.place_type = place_type
    place.status = data.status
    place.metadata_ = metadata
    if data.lat is not None and data.lon is not None:
        from geoalchemy2.elements import WKTElement
        place.geom = WKTElement(f"POINT({data.lon} {data.lat})", srid=4326)

    await flush_record(db, place)
    await sync_schema_relations(db, "place", place.id, metadata)
    await log_change(db, record_type="place", record_id=place.id, user_id=current_user.id, action="update",
                     changed_fields={"old": old, "new": {"idno": data.idno, "place_type": place_type, "status": data.status}})
    try:
        await search_service.index_record("place", place, db)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    return place


@router.post(
    "/{place_id}/publish",
    summary="Publish a place after validating required fields",
    responses={
        403: {"description": "Insufficient permissions"},
    },
)
async def publish_place(
    place_id: uuid.UUID,
    db: DBDep,
    current_user=require_record_permission("place", "update"),
) -> dict:
    """Publish a place after validating required fields."""
    ok, errors = await can_publish(db, "place", str(place_id))
    if not ok:
        raise HTTPException(status_code=422, detail={"errors": errors})
    result = await publish_record(db, "place", str(place_id), str(current_user.id))
    await db.commit()
    return result


@router.delete(
    "/{place_id}",
    status_code=204,
    summary="Delete a place record",
    responses={
        404: {"description": "Place not found"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Record has linked relations (pass force=true to delete anyway)"},
    },
)
async def delete_place(
    place_id: uuid.UUID,
    db: DBDep,
    current_user=require_record_permission("place", "delete"),
    force: bool = Query(False),
) -> None:
    result = await db.execute(select(Place).where(Place.id == place_id))
    place = result.scalar_one_or_none()
    if not place:
        raise HTTPException(status_code=404, detail="Ort nicht gefunden")

    related_count = await count_relations(db, "place", place_id)
    if related_count > 0 and not force:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": f"Dieser Datensatz ist mit {related_count} anderen Datensätzen verknüpft.",
                "related_count": related_count,
            },
        )

    if related_count > 0:
        await delete_relations(db, "place", place_id)

    await log_change(db, record_type="place", record_id=place.id, user_id=current_user.id, action="delete")
    await db.delete(place)
    await flush_record(db, place)
    try:
        await search_service.remove_record(place.id)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)

    from katalon.workers.cleanup_tasks import cleanup_relation_refs
    from katalon.workers.enqueue import enqueue
    enqueue(cleanup_relation_refs, "place", str(place_id))


@router.post(
    "/{place_id}/snapshots",
    response_model=SnapshotRead,
    status_code=201,
    summary="Create a snapshot of the current place state",
    responses={
        404: {"description": "Place not found"},
        403: {"description": "Insufficient permissions"},
    },
)
async def create_snapshot(
    place_id: uuid.UUID, data: SnapshotCreate, db: DBDep, current_user=require_record_permission("place", "update")
) -> RecordSnapshot:
    result = await db.execute(select(Place).where(Place.id == place_id))
    place = result.scalar_one_or_none()
    if not place:
        raise HTTPException(status_code=404, detail="Ort nicht gefunden")
    snap = RecordSnapshot(
        record_type="place",
        record_id=place.id,
        label=data.label,
        snapshot={
            "idno": place.idno,
            "place_type": place.place_type,
            "status": place.status,
            "metadata": place.metadata_,
        },
        created_by=current_user.id,
    )
    db.add(snap)
    await db.flush()
    return snap


@router.get(
    "/{place_id}/snapshots",
    response_model=list[SnapshotRead],
    summary="List snapshots for a place",
)
async def list_snapshots(place_id: uuid.UUID, db: DBDep) -> list[RecordSnapshot]:
    result = await db.execute(
        select(RecordSnapshot)
        .where(RecordSnapshot.record_type == "place", RecordSnapshot.record_id == place_id)
        .order_by(RecordSnapshot.created_at.desc())
    )
    return list(result.scalars().all())


@router.post(
    "/{place_id}/snapshots/{snapshot_id}/restore",
    response_model=PlaceRead,
    summary="Restore a place from a snapshot",
    responses={
        404: {"description": "Place or snapshot not found"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Version conflict"},
        428: {"description": "If-Match header required"},
    },
)
async def restore_snapshot(
    place_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    db: DBDep,
    current_user=require_record_permission("place", "update"),
    if_match: int | None = Header(None, alias="If-Match"),
) -> Place:
    snap_result = await db.execute(
        select(RecordSnapshot).where(
            RecordSnapshot.id == snapshot_id,
            RecordSnapshot.record_type == "place",
            RecordSnapshot.record_id == place_id,
        )
    )
    snap = snap_result.scalar_one_or_none()
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot nicht gefunden")

    place_result = await db.execute(select(Place).where(Place.id == place_id))
    place = place_result.scalar_one_or_none()
    if not place:
        raise HTTPException(status_code=404, detail="Ort nicht gefunden")
    require_version(place.version, if_match)

    data = snap.snapshot
    if "idno" in data:
        place.idno = data["idno"]
    if "place_type" in data:
        place.place_type = data["place_type"]
    if "status" in data:
        place.status = data["status"]
    if "metadata" in data:
        place.metadata_ = data["metadata"]
    flag_modified(place, "metadata_")
    await flush_record(db, place)
    await sync_schema_relations(db, "place", place.id, place.metadata_)
    await log_change(
        db,
        record_type="place",
        record_id=place.id,
        user_id=current_user.id,
        action="restore",
        changed_fields={"snapshot_id": str(snapshot_id)},
    )
    await db.commit()
    try:
        await search_service.index_record("place", place, db)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    return place


@router.get(
    "/{place_id}/audit-log",
    response_model=list[AuditLogRead],
    summary="List audit log entries for a place",
)
async def list_place_audit_log(place_id: uuid.UUID, db: DBDep) -> list[AuditLogRead]:
    from katalon.api.v1.audit import list_audit_log
    return await list_audit_log(db, record_type="place", record_id=place_id, limit=100)
