import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import func, select

logger = logging.getLogger(__name__)

from katalon.core.dependencies import CurrentUser, DBDep, OptionalCurrentUser
from katalon.core.models import AdminConfig, FieldDefinition, MediaFile, Object, RecordSnapshot
from katalon.core.schemas import (
    AuditLogRead,
    ObjectCreate,
    ObjectRead,
    SnapshotCreate,
    SnapshotRead,
)
from katalon.services import search_service
from katalon.services.audit_service import log_change
from katalon.services.idno_service import consume_next_idno, maybe_advance_counter, validate_idno_pattern
from katalon.services.relation_service import count_relations, delete_relations
from katalon.services.schema_service import validate_metadata
from katalon.services.subtype_service import ensure_subtype_exists, normalize_subtype_name

router = APIRouter(prefix="/objects", tags=["objects"])


_PUBLIC_STATUSES = ("public", "published")


@router.get("", response_model=dict)
async def list_objects(
    db: DBDep,
    current_user: OptionalCurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: str | None = None,
    object_type: str | None = None,
    q: str | None = None,
) -> dict:
    query = select(Object)
    if status:
        query = query.where(Object.status == status)
    if object_type:
        query = query.where(Object.object_type == object_type)
    elif current_user is None:
        query = query.where(Object.status.in_(_PUBLIC_STATUSES))
    if q:
        query = query.where(Object.search_vector.match(q))

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar_one()

    query = query.offset((page - 1) * page_size).limit(page_size).order_by(Object.updated_at.desc())
    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [ObjectRead.model_validate(i) for i in items],
    }


@router.post("", response_model=ObjectRead, status_code=201)
async def create_object(data: ObjectCreate, db: DBDep, current_user: CurrentUser) -> Object:
    cfg_result = await db.execute(select(AdminConfig).where(AdminConfig.key == "default"))
    cfg = cfg_result.scalar_one_or_none()
    schema = (cfg.idno_schemas or {}).get("object") if cfg else None
    pattern = (cfg.idno_patterns or {}).get("object") if cfg else None

    if not data.idno or not data.idno.strip():
        if schema:
            idno = await consume_next_idno(db, "object", schema)
        else:
            raise HTTPException(status_code=422, detail="ID-Nr. ist ein Pflichtfeld.")
    else:
        idno = data.idno.strip()
        if pattern and not validate_idno_pattern(pattern, idno):
            raise HTTPException(status_code=422, detail=f"ID-Nr. entspricht nicht dem Muster: {pattern}")
        if schema:
            await maybe_advance_counter(db, "object", schema, idno)

    object_type = normalize_subtype_name(data.object_type, allow_null=True)
    await ensure_subtype_exists(db, "object", object_type)
    errors = await validate_metadata(db, "object", data.metadata_, object_type)
    if errors:
        raise HTTPException(status_code=422, detail=errors)

    existing = await db.execute(select(Object).where(Object.idno == idno))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="ID-Nr. bereits vergeben.")

    obj = Object(
        idno=idno,
        object_type=object_type,
        status=data.status,
        metadata_=data.metadata_,
    )
    db.add(obj)
    await db.flush()
    await log_change(db, record_type="object", record_id=obj.id, user_id=current_user.id, action="create")
    try:
        await search_service.index_record("object", obj, db)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    return obj


@router.get("/{object_id}", response_model=ObjectRead)
async def get_object(object_id: uuid.UUID, db: DBDep, current_user: OptionalCurrentUser) -> Object:
    result = await db.execute(select(Object).where(Object.id == object_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden")
    if current_user is None and obj.status not in _PUBLIC_STATUSES:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden")
    return obj


@router.put("/{object_id}", response_model=ObjectRead)
async def update_object(
    object_id: uuid.UUID, data: ObjectCreate, db: DBDep, current_user: CurrentUser
) -> Object:
    if not data.idno or not data.idno.strip():
        raise HTTPException(status_code=422, detail="ID-Nr. ist ein Pflichtfeld.")
    result = await db.execute(select(Object).where(Object.id == object_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden")

    existing = await db.execute(select(Object).where(Object.idno == data.idno.strip(), Object.id != object_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="ID-Nr. bereits vergeben.")

    object_type = normalize_subtype_name(data.object_type, allow_null=True)
    await ensure_subtype_exists(db, "object", object_type)
    errors = await validate_metadata(db, "object", data.metadata_, object_type)
    if errors:
        raise HTTPException(status_code=422, detail=errors)

    old_fields = {
        "idno": obj.idno,
        "object_type": obj.object_type,
        "status": obj.status,
        "metadata": obj.metadata_,
    }
    obj.idno = data.idno.strip()
    obj.object_type = object_type
    obj.status = data.status
    obj.metadata_ = data.metadata_

    await log_change(
        db,
        record_type="object",
        record_id=obj.id,
        user_id=current_user.id,
        action="update",
        changed_fields={
            "old": old_fields,
            "new": {
                "object_type": object_type,
                "status": data.status,
                "metadata": data.metadata_,
            },
        },
    )
    try:
        await search_service.index_record("object", obj, db)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    return obj


@router.delete("/{object_id}", status_code=204)
async def delete_object(
    object_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentUser,
    force: bool = Query(False),
) -> None:
    result = await db.execute(select(Object).where(Object.id == object_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden")

    related_count = await count_relations(db, "object", object_id)
    if related_count > 0 and not force:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": f"Dieser Datensatz ist mit {related_count} anderen Datensätzen verknüpft.",
                "related_count": related_count,
            },
        )

    if related_count > 0:
        await delete_relations(db, "object", object_id)

    await log_change(db, record_type="object", record_id=obj.id, user_id=current_user.id, action="delete")
    try:
        await search_service.remove_record(obj.id)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    await db.delete(obj)

    from katalon.workers.cleanup_tasks import cleanup_relation_refs
    cleanup_relation_refs.delay("object", str(object_id))


@router.post("/{object_id}/snapshots", response_model=SnapshotRead, status_code=201)
async def create_snapshot(
    object_id: uuid.UUID, data: SnapshotCreate, db: DBDep, current_user: CurrentUser
) -> RecordSnapshot:
    result = await db.execute(select(Object).where(Object.id == object_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden")

    snap = RecordSnapshot(
        record_type="object",
        record_id=obj.id,
        label=data.label,
        snapshot={
            "idno": obj.idno,
            "object_type": obj.object_type,
            "status": obj.status,
            "metadata": obj.metadata_,
        },
        created_by=current_user.id,
    )
    db.add(snap)
    await db.flush()
    return snap


@router.get("/{object_id}/iiif/manifest")
async def iiif_manifest(object_id: uuid.UUID, db: DBDep, request: Request) -> dict:
    from katalon.integrations.cantaloupe import build_object_manifest
    from katalon.config import settings

    obj_result = await db.execute(select(Object).where(Object.id == object_id))
    obj = obj_result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden")
    if obj.status not in ("public", "published"):
        raise HTTPException(status_code=404, detail="Kein IIIF-Manifest verfügbar")

    media_result = await db.execute(
        select(MediaFile)
        .where(MediaFile.object_id == object_id, MediaFile.status == "ready")
        .order_by(MediaFile.is_primary.desc(), MediaFile.created_at)
    )
    media_files = media_result.scalars().all()
    if not media_files:
        raise HTTPException(status_code=404, detail="Kein IIIF-Manifest verfügbar")

    field_result = await db.execute(
        select(FieldDefinition)
        .where(FieldDefinition.target_type == "object", FieldDefinition.show_in_detail == True)  # noqa: E712
        .order_by(FieldDefinition.sort_order)
    )
    field_defs = field_result.scalars().all()

    media_items = [(Path(m.file_path).name, m.iiif_manifest) for m in media_files]
    manifest_id = str(request.url)
    portal_url = settings.katalon_base_url.rstrip("/")
    homepage_url = f"{portal_url}/objects/{object_id}" if portal_url else None

    return build_object_manifest(
        manifest_id,
        media_items,
        obj=obj,
        field_defs=list(field_defs),
        homepage_url=homepage_url,
    )


@router.get("/{object_id}/snapshots", response_model=list[SnapshotRead])
async def list_snapshots(object_id: uuid.UUID, db: DBDep) -> list[RecordSnapshot]:
    result = await db.execute(
        select(RecordSnapshot)
        .where(RecordSnapshot.record_type == "object", RecordSnapshot.record_id == object_id)
        .order_by(RecordSnapshot.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/{object_id}/snapshots/{snapshot_id}/restore", response_model=ObjectRead)
async def restore_snapshot(
    object_id: uuid.UUID, snapshot_id: uuid.UUID, db: DBDep, _: CurrentUser
) -> Object:
    snap_result = await db.execute(
        select(RecordSnapshot).where(
            RecordSnapshot.id == snapshot_id,
            RecordSnapshot.record_type == "object",
            RecordSnapshot.record_id == object_id,
        )
    )
    snap = snap_result.scalar_one_or_none()
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot nicht gefunden")

    obj_result = await db.execute(select(Object).where(Object.id == object_id))
    obj = obj_result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden")

    data = snap.snapshot
    if "idno" in data:
        obj.idno = data["idno"]
    if "status" in data:
        obj.status = data["status"]
    if "object_type" in data:
        obj.object_type = data["object_type"]
    if "metadata" in data:
        obj.metadata_ = data["metadata"]
    await db.flush()
    return obj


@router.get("/{object_id}/audit-log", response_model=list[AuditLogRead])
async def list_object_audit_log(object_id: uuid.UUID, db: DBDep) -> list[AuditLogRead]:
    from katalon.api.v1.audit import list_audit_log
    return await list_audit_log(db, record_type="object", record_id=object_id, limit=100)
