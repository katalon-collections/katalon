import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, Request
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
from katalon.core.models import (
    AdminConfig,
    FieldDefinition,
    MediaFile,
    Object,
    RecordSnapshot,
    User,
)
from katalon.core.schemas import (
    AuditLogRead,
    ObjectCreate,
    ObjectRead,
    SnapshotCreate,
    SnapshotRead,
)
from katalon.core.visibility import apply_public_visibility, ensure_publicly_visible
from katalon.services import search_service
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
    has_any_subtypes,
    normalize_subtype_name,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/objects", tags=["objects"])
COLLECTION_STATUSES = {"active", "pending", "on_loan_in", "on_loan_out", "deaccessioned", "returned"}


async def _visibility_user(db: DBDep, user: OptionalCurrentUser) -> User | None:
    return user if user and await has_record_permission(db, user, "object", "read") else None


@router.get(
    "",
    response_model=dict[str, Any],
    summary="List objects with pagination and filters",
)
async def list_objects(
    db: DBDep,
    current_user: OptionalCurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: str | None = None,
    object_type: str | None = None,
    q: str | None = None,
) -> dict[str, Any]:
    query = select(Object)
    if status:
        query = query.where(Object.status == status)
    visibility_user = await _visibility_user(db, current_user)
    query = apply_public_visibility(query, Object, visibility_user)
    if object_type:
        query = query.where(Object.object_type == object_type)
    if q:
        query = query.where(
            Object.idno.icontains(q, autoescape=True)
            | cast(Object.metadata_, Text).icontains(q, autoescape=True)
        )

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar_one()

    query = query.offset((page - 1) * page_size).limit(page_size).order_by(Object.updated_at.desc())
    result = await db.execute(query)
    items = result.scalars().all()

    response_items = [ObjectRead.model_validate(i) for i in items]
    if visibility_user is None:
        response_items = [
            await project_public_record(db, item, "object", obj.object_type)
            for item, obj in zip(response_items, items, strict=True)
        ]
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": response_items,
    }


@router.post(
    "",
    response_model=ObjectRead,
    status_code=201,
    summary="Create a new object record",
    responses={
        403: {"description": "Insufficient permissions"},
        400: {"description": "Idno already taken"},
        422: {"description": "Idno missing/invalid pattern or metadata validation failed"},
    },
)
async def create_object(data: ObjectCreate, db: DBDep, current_user: User = require_record_permission("object", "create")) -> Object:
    cfg_result = await db.execute(select(AdminConfig).where(AdminConfig.key == "default"))
    cfg = cfg_result.scalar_one_or_none()
    schema = (cfg.idno_schemas or {}).get("object") if cfg else None
    pattern = (cfg.idno_patterns or {}).get("object") if cfg else None

    if not data.idno or not data.idno.strip():
        if schema:
            idno = await consume_next_idno(db, "object", schema)
        elif data.status == "draft":
            idno = None
        else:
            raise HTTPException(status_code=422, detail="ID-Nr. ist ein Pflichtfeld.")
    else:
        idno = data.idno.strip()
        if pattern and not validate_idno_pattern(pattern, idno):
            raise HTTPException(status_code=422, detail=f"ID-Nr. entspricht nicht dem Muster: {pattern}")
        if schema:
            await maybe_advance_counter(db, "object", schema, idno)

    _has_subtypes = await has_any_subtypes(db, "object")
    object_type = normalize_subtype_name(
        data.object_type,
        allow_null=data.status == "draft" or not _has_subtypes,
    )
    await ensure_subtype_exists(db, "object", object_type)
    metadata = await prepare_metadata(
        db, "object", data.metadata_, object_type,
        can_edit_locked=current_user.role in {"admin", "superuser"},
    )
    errors = await validate_metadata(
        db, "object", metadata, object_type, skip_required=data.status == "draft"
    )
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    if data.collection_status not in COLLECTION_STATUSES:
        raise HTTPException(status_code=422, detail="Ungültiger Sammlungsstatus.")

    if idno is not None:
        existing = await db.execute(select(Object).where(Object.idno == idno))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="ID-Nr. bereits vergeben.")

    obj = Object(
        idno=idno,
        object_type=object_type,
        collection_status=data.collection_status,
        status=data.status,
        metadata_=metadata,
    )
    db.add(obj)
    await flush_record(db, obj)
    await sync_schema_relations(db, "object", obj.id, metadata)
    await db.flush()
    await log_change(db, record_type="object", record_id=obj.id, user_id=current_user.id, action="create")
    try:
        await search_service.index_record("object", obj, db)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    return obj


@router.get(
    "/{object_id}",
    response_model=ObjectRead,
    summary="Get a single object by ID",
    responses={
        404: {"description": "Object not found"},
    },
)
async def get_object(object_id: uuid.UUID, db: DBDep, current_user: OptionalCurrentUser) -> Object | ObjectRead:
    result = await db.execute(select(Object).where(Object.id == object_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden")
    visibility_user = await _visibility_user(db, current_user)
    ensure_publicly_visible(obj, visibility_user, "Objekt nicht gefunden")
    if visibility_user is None:
        return await project_public_record(db, ObjectRead.model_validate(obj), "object", obj.object_type)
    return obj


@router.put(
    "/{object_id}",
    response_model=ObjectRead,
    summary="Update an object record",
    responses={
        404: {"description": "Object not found"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Version conflict (If-Match mismatch)"},
        400: {"description": "Idno already taken"},
        422: {"description": "Idno missing or metadata validation failed"},
    },
)
async def update_object(
    object_id: uuid.UUID,
    data: ObjectCreate,
    db: DBDep,
    current_user: User = require_record_permission("object", "update"),
    if_match: int | None = Header(None, alias="If-Match"),
) -> Object:
    result = await db.execute(select(Object).where(Object.id == object_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden")
    check_version(obj.version, if_match)

    if not data.idno or not data.idno.strip():
        if data.status == "draft":
            idno = None
        else:
            raise HTTPException(status_code=422, detail="ID-Nr. ist ein Pflichtfeld.")
    else:
        idno = data.idno.strip()
        existing = await db.execute(select(Object).where(Object.idno == idno, Object.id != object_id))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="ID-Nr. bereits vergeben.")

    _has_subtypes = await has_any_subtypes(db, "object")
    object_type = normalize_subtype_name(
        data.object_type,
        allow_null=data.status == "draft" or not _has_subtypes,
    )
    await ensure_subtype_exists(db, "object", object_type)
    metadata = await prepare_metadata(
        db, "object", data.metadata_, object_type, existing=obj.metadata_,
        can_edit_locked=current_user.role in {"admin", "superuser"},
    )
    errors = await validate_metadata(
        db, "object", metadata, object_type, skip_required=data.status == "draft"
    )
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    if data.collection_status not in COLLECTION_STATUSES:
        raise HTTPException(status_code=422, detail="Ungültiger Sammlungsstatus.")

    old_fields = {
        "idno": obj.idno,
        "object_type": obj.object_type,
        "collection_status": obj.collection_status,
        "status": obj.status,
        "metadata": obj.metadata_,
    }
    obj.idno = idno
    obj.object_type = object_type
    obj.collection_status = data.collection_status
    obj.status = data.status
    obj.metadata_ = metadata

    await flush_record(db, obj)

    await sync_schema_relations(db, "object", obj.id, metadata)

    update_diff = diff_fields(
        old_fields,
        {
            "idno": idno,
            "object_type": object_type,
            "collection_status": data.collection_status,
            "status": data.status,
            "metadata": metadata,
        },
    )
    if update_diff:
        await log_change(
            db,
            record_type="object",
            record_id=obj.id,
            user_id=current_user.id,
            action="update",
            changed_fields=update_diff,
        )
    try:
        await search_service.index_record("object", obj, db)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    return obj


@router.post(
    "/{object_id}/publish",
    summary="Publish an object after validating required fields",
    responses={
        403: {"description": "Insufficient permissions"},
    },
)
async def publish_object(
    object_id: uuid.UUID,
    db: DBDep,
    current_user: User = require_record_permission("object", "update"),
) -> dict[str, Any]:
    """Publish an object after validating required fields."""
    ok, errors = await can_publish(db, "object", str(object_id))
    if not ok:
        raise HTTPException(status_code=422, detail={"errors": errors})
    result = await publish_record(db, "object", str(object_id), str(current_user.id))
    await db.commit()
    return result


@router.delete(
    "/{object_id}",
    status_code=204,
    summary="Delete an object record",
    responses={
        404: {"description": "Object not found"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Record has linked relations (pass force=true to delete anyway)"},
    },
)
async def delete_object(
    object_id: uuid.UUID,
    db: DBDep,
    current_user: User = require_record_permission("object", "delete"),
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

    obj.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    await log_change(
        db, record_type="object", record_id=obj.id, user_id=current_user.id, action="delete",
        changed_fields=delete_label_fields(obj.idno, obj.metadata_),
    )
    await flush_record(db, obj)
    try:
        await search_service.remove_record(obj.id)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)

    from katalon.workers.cleanup_tasks import cleanup_relation_refs
    from katalon.workers.enqueue import enqueue
    enqueue(cleanup_relation_refs, "object", str(object_id))


@router.post(
    "/{object_id}/restore",
    response_model=ObjectRead,
    summary="Restore a soft-deleted object",
    responses={
        404: {"description": "Object not found or not deleted"},
        403: {"description": "Insufficient permissions"},
    },
)
async def restore_object(
    object_id: uuid.UUID,
    db: DBDep,
    current_user: User = require_role("admin"),
) -> Object:
    result = await db.execute(select(Object).where(Object.id == object_id))
    obj = result.scalar_one_or_none()
    if not obj or obj.deleted_at is None:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden")
    obj.deleted_at = None
    await log_change(db, record_type="object", record_id=obj.id, user_id=current_user.id, action="undelete")
    await flush_record(db, obj)
    try:
        await search_service.index_record("object", obj, db)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    return obj


@router.get(
    "/trash/list",
    response_model=list[ObjectRead],
    summary="List soft-deleted objects",
)
async def list_deleted_objects(db: DBDep, current_user: User = require_role("admin")) -> list[Object]:
    result = await db.execute(
        select(Object).where(Object.deleted_at.is_not(None)).order_by(Object.deleted_at.desc())
    )
    return list(result.scalars().all())


@router.post(
    "/{object_id}/snapshots",
    response_model=SnapshotRead,
    status_code=201,
    summary="Create a snapshot of the current object state",
    responses={
        404: {"description": "Object not found"},
        403: {"description": "Insufficient permissions"},
    },
)
async def create_snapshot(
    object_id: uuid.UUID, data: SnapshotCreate, db: DBDep, current_user: User = require_record_permission("object", "update")
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
            "collection_status": obj.collection_status,
            "status": obj.status,
            "metadata": obj.metadata_,
        },
        created_by=current_user.id,
    )
    db.add(snap)
    await db.flush()
    return snap


@router.get(
    "/{object_id}/iiif/manifest",
    summary="Get IIIF presentation manifest for an object",
    responses={
        404: {"description": "Object or IIIF manifest not found"},
    },
)
async def iiif_manifest(object_id: uuid.UUID, db: DBDep, request: Request, *, portal_only: bool = False) -> dict[str, Any]:
    from katalon.config import settings
    from katalon.integrations.cantaloupe import build_object_manifest
    from katalon.services.public_metadata_service import filter_public_metadata, load_public_fields

    obj_result = await db.execute(select(Object).where(Object.id == object_id))
    obj = obj_result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden")
    if obj.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Kein IIIF-Manifest verfügbar")
    if obj.status not in ("public", "published") or (portal_only and obj.collection_status != "active"):
        raise HTTPException(status_code=404, detail="Kein IIIF-Manifest verfügbar")

    media_result = await db.execute(
        select(MediaFile)
        .where(MediaFile.object_id == object_id, MediaFile.status == "ready")
        .order_by(MediaFile.is_primary.desc(), MediaFile.created_at)
    )
    from katalon.core.media_validation import media_category

    media_files = [m for m in media_result.scalars().all() if media_category(m.mime_type) == "image"]
    if not media_files:
        raise HTTPException(status_code=404, detail="Kein IIIF-Manifest verfügbar")

    field_result = await db.execute(
        select(FieldDefinition)
        .where(
            FieldDefinition.target_type == "object",
            FieldDefinition.show_in_detail == True,  # noqa: E712
            FieldDefinition.is_public.is_(True),
            FieldDefinition.is_deleted.is_(False),
        )
        .order_by(FieldDefinition.sort_order)
    )
    field_defs = field_result.scalars().all()
    public_fields = await load_public_fields(db, "object")
    public_metadata = filter_public_metadata(obj.metadata_, public_fields, obj.object_type)

    media_items = [(Path(m.file_path).name, m.iiif_manifest) for m in media_files]
    portal_url = settings.katalon_base_url.rstrip("/")
    manifest_id = f"{portal_url}{request.url.path}" if portal_url else str(request.url)
    homepage_url = f"{portal_url}/objects/{object_id}" if portal_url else None

    return build_object_manifest(
        manifest_id,
        media_items,
        obj=obj,
        field_defs=list(field_defs),
        homepage_url=homepage_url,
        metadata=public_metadata,
    )


@router.get(
    "/{object_id}/snapshots",
    response_model=list[SnapshotRead],
    summary="List snapshots for an object",
)
async def list_snapshots(object_id: uuid.UUID, db: DBDep) -> list[RecordSnapshot]:
    result = await db.execute(
        select(RecordSnapshot)
        .where(RecordSnapshot.record_type == "object", RecordSnapshot.record_id == object_id)
        .order_by(RecordSnapshot.created_at.desc())
    )
    return list(result.scalars().all())


@router.post(
    "/{object_id}/snapshots/{snapshot_id}/restore",
    response_model=ObjectRead,
    summary="Restore an object from a snapshot",
    responses={
        404: {"description": "Object or snapshot not found"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Version conflict"},
        428: {"description": "If-Match header required"},
    },
)
async def restore_snapshot(
    object_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    db: DBDep,
    current_user: User = require_record_permission("object", "update"),
    if_match: int | None = Header(None, alias="If-Match"),
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
    require_version(obj.version, if_match)

    data = snap.snapshot
    if "idno" in data:
        obj.idno = data["idno"]
    if "status" in data:
        obj.status = data["status"]
    if "object_type" in data:
        obj.object_type = data["object_type"]
    if "collection_status" in data:
        obj.collection_status = data["collection_status"]
    if "metadata" in data:
        obj.metadata_ = data["metadata"]
    flag_modified(obj, "metadata_")
    await flush_record(db, obj)
    await sync_schema_relations(db, "object", obj.id, obj.metadata_)
    await log_change(
        db,
        record_type="object",
        record_id=obj.id,
        user_id=current_user.id,
        action="restore",
        changed_fields={"snapshot_id": str(snapshot_id)},
    )
    await db.commit()
    try:
        await search_service.index_record("object", obj, db)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    return obj


@router.get(
    "/{object_id}/audit-log",
    response_model=list[AuditLogRead],
    summary="List audit log entries for an object",
)
async def list_object_audit_log(object_id: uuid.UUID, db: DBDep) -> list[AuditLogRead]:
    from katalon.api.v1.audit import list_audit_log
    return await list_audit_log(db, record_type="object", record_id=object_id, limit=100)
