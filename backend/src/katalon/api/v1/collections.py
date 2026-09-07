# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from sqlalchemy import Text, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from katalon.config import settings
from katalon.core.concurrency import check_version, flush_record, require_version
from katalon.core.dependencies import (
    DBDep,
    OptionalCurrentUser,
    has_record_permission,
    require_record_permission,
    require_role,
)
from katalon.core.limiter import limiter
from katalon.core.list_query import SortBy, SortDir, apply_sort
from katalon.core.models import AdminConfig, Collection, RecordSnapshot, User
from katalon.core.schemas import (
    AuditLogRead,
    CollectionCreate,
    CollectionRead,
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

router = APIRouter(prefix="/collections", tags=["collections"])
#: Statuses that make a record publicly visible and trigger PID auto-minting.
PUBLIC_SAVE_STATUSES = set(PUBLIC_STATUSES)


async def _visibility_user(db: DBDep, user: OptionalCurrentUser) -> User | None:
    return user if user and await has_record_permission(db, user, "collection", "read") else None


async def _validate_parent_id(
    db: AsyncSession,
    collection_id: uuid.UUID | None,
    parent_id: uuid.UUID | None,
) -> None:
    if parent_id is None:
        return
    if collection_id is not None and parent_id == collection_id:
        raise HTTPException(
            status_code=422,
            detail="Eine Sammlung kann nicht ihre eigene übergeordnete Sammlung sein.",
        )

    parent = (
        await db.execute(
            select(Collection).where(
                Collection.id == parent_id,
                Collection.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if parent is None:
        raise HTTPException(
            status_code=422,
            detail="Übergeordnete Sammlung existiert nicht.",
        )

    if collection_id is not None:
        curr_parent_id: uuid.UUID | None = parent.parent_id
        visited: set[uuid.UUID] = {collection_id, parent_id}
        while curr_parent_id is not None:
            if curr_parent_id == collection_id:
                raise HTTPException(
                    status_code=422,
                    detail="Zyklische Sammlungshierarchie ist nicht erlaubt.",
                )
            if curr_parent_id in visited:
                break
            visited.add(curr_parent_id)
            curr_parent_id = (
                await db.execute(
                    select(Collection.parent_id).where(Collection.id == curr_parent_id)
                )
            ).scalar_one_or_none()


@router.get(
    "",
    response_model=dict[str, Any],
    summary="List collections with pagination and filters",
)
async def list_collections(
    db: DBDep,
    current_user: OptionalCurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    collection_type: str | None = None,
    status: str | None = None,
    parent_id: uuid.UUID | None = None,
    q: str | None = None,
    sort_by: SortBy | None = None,
    sort_dir: SortDir = "desc",
) -> dict[str, Any]:
    query = select(Collection)
    if collection_type:
        query = query.where(Collection.collection_type == collection_type)
    if status:
        query = query.where(Collection.status == status)
    if parent_id is not None:
        query = query.where(Collection.parent_id == parent_id)
    visibility_user = await _visibility_user(db, current_user)
    query = apply_public_visibility(query, Collection, visibility_user)
    if q:
        query = query.where(
            Collection.idno.icontains(q, autoescape=True)
            | cast(Collection.metadata_, Text).icontains(q, autoescape=True)
        )
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    query = apply_sort(
        query.offset((page - 1) * page_size).limit(page_size),
        Collection,
        sort_by,
        sort_dir,
    )
    items = (await db.execute(query)).scalars().all()
    response_items = [CollectionRead.model_validate(i) for i in items]
    if visibility_user is None:
        response_items = [
            await project_public_record(db, item, "collection", col.collection_type)
            for item, col in zip(response_items, items, strict=True)
        ]
    return {"total": total, "page": page, "page_size": page_size, "items": response_items}


@router.post(
    "",
    response_model=CollectionRead,
    status_code=201,
    summary="Create a new collection record",
    responses={
        403: {"description": "Insufficient permissions"},
        400: {"description": "Idno already taken"},
        422: {"description": "Idno missing/invalid pattern or metadata validation failed"},
    },
)
async def create_collection(
    data: CollectionCreate,
    db: DBDep,
    current_user: User = require_record_permission("collection", "create"),
) -> Collection:
    cfg_result = await db.execute(select(AdminConfig).where(AdminConfig.key == "default"))
    cfg = cfg_result.scalar_one_or_none()
    schema = (cfg.idno_schemas or {}).get("collection") if cfg else None
    pattern = (cfg.idno_patterns or {}).get("collection") if cfg else None

    if not data.idno or not data.idno.strip():
        if schema:
            idno = await consume_next_idno(db, "collection", schema)
        elif data.status == "draft":
            idno = None
        else:
            raise HTTPException(status_code=422, detail="ID-Nr. ist ein Pflichtfeld.")
    else:
        idno = data.idno.strip()
        if pattern and not validate_idno_pattern(pattern, idno):
            raise HTTPException(
                status_code=422,
                detail="ID-Nr. entspricht nicht dem vorgegebenen Muster.",
            )
        if schema:
            await maybe_advance_counter(db, "collection", schema, idno)
        existing = await db.execute(select(Collection).where(Collection.idno == idno))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="ID-Nr. bereits vergeben.")

    await _validate_parent_id(db, None, data.parent_id)

    collection_type = normalize_subtype_name(
        data.collection_type,
        allow_null=True,
    )
    await ensure_subtype_exists(db, "collection", collection_type)
    metadata = await prepare_metadata(
        db, "collection", data.metadata_, collection_type, existing=None,
        can_edit_locked=current_user.role in {"admin", "superuser"},
    )
    errors = await validate_metadata(
        db, "collection", metadata, collection_type, skip_required=data.status == "draft"
    )
    if errors:
        raise HTTPException(status_code=422, detail=errors)

    col = Collection(
        idno=idno,
        collection_type=collection_type,
        parent_id=data.parent_id,
        status=data.status,
        metadata_=metadata,
    )
    db.add(col)
    await flush_record(db, col)
    await sync_schema_relations(db, "collection", col.id, metadata)
    await log_change(
        db,
        record_type="collection",
        record_id=col.id,
        user_id=current_user.id,
        action="create",
    )
    if data.status in PUBLIC_SAVE_STATUSES:
        try:
            await pid_service.ensure_pids_on_publish(db, "collection", col, current_user.id)
        except pid_service.PidMintError as exc:
            raise HTTPException(status_code=422, detail=f"PID-Vergabe fehlgeschlagen: {exc}") from exc
    try:
        await search_service.index_record("collection", col, db)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    return col


@limiter.limit(lambda: settings.rate_limit_public_export)
@router.get(
    "/{col_id}/export",
    summary="Export a single collection record as JSON-LD or Turtle RDF",
)
async def export_collection(
    col_id: uuid.UUID,
    db: DBDep,
    request: Request,
    current_user: OptionalCurrentUser,
    format: str | None = Query(None),
    accept: str | None = Header(None),
) -> Response:
    from katalon.services.rdf_service import handle_single_record_export

    return await handle_single_record_export(
        "collection",
        col_id,
        db,
        request,
        current_user=current_user,
        format_param=format,
        accept_header=accept,
    )


@router.get(
    "/{col_id}",
    response_model=CollectionRead,
    summary="Get a single collection by ID",
    responses={
        404: {"description": "Collection not found"},
    },
)
async def get_collection(
    col_id: uuid.UUID,
    db: DBDep,
    current_user: OptionalCurrentUser,
    request: Request = None,  # type: ignore[assignment]
    format: str | None = Query(None),
    accept: str | None = Header(None),
) -> Any:
    is_rdf_format = isinstance(format, str) and format.lower() in ("jsonld", "json-ld", "ttl", "turtle")
    is_rdf_accept = isinstance(accept, str) and ("application/ld+json" in accept or "text/turtle" in accept)
    if is_rdf_format or is_rdf_accept:
        from katalon.services.rdf_service import handle_single_record_export

        return await handle_single_record_export(
            "collection",
            col_id,
            db,
            request,
            current_user=current_user,
            format_param=format if isinstance(format, str) else None,
            accept_header=accept if isinstance(accept, str) else None,
        )

    result = await db.execute(select(Collection).where(Collection.id == col_id))
    col = result.scalar_one_or_none()
    if not col:
        raise HTTPException(status_code=404, detail="Sammlung nicht gefunden")
    visibility_user = await _visibility_user(db, current_user)
    ensure_publicly_visible(col, visibility_user, "Sammlung nicht gefunden")
    if visibility_user is None:
        return await project_public_record(
            db, CollectionRead.model_validate(col), "collection", col.collection_type
        )
    return col


@router.put(
    "/{col_id}",
    response_model=CollectionRead,
    summary="Update a collection record",
    responses={
        404: {"description": "Collection not found"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Version conflict (If-Match mismatch)"},
        400: {"description": "Idno already taken"},
        422: {"description": "Idno missing or metadata validation failed"},
    },
)
async def update_collection(
    col_id: uuid.UUID,
    data: CollectionCreate,
    db: DBDep,
    current_user: User = require_record_permission("collection", "update"),
    if_match: int | None = Header(None, alias="If-Match"),
) -> Collection:
    result = await db.execute(select(Collection).where(Collection.id == col_id))
    col = result.scalar_one_or_none()
    if not col:
        raise HTTPException(status_code=404, detail="Sammlung nicht gefunden")
    check_version(col.version, if_match)

    if not data.idno or not data.idno.strip():
        if data.status == "draft":
            idno = None
        else:
            raise HTTPException(status_code=422, detail="ID-Nr. ist ein Pflichtfeld.")
    else:
        idno = data.idno.strip()
        existing = await db.execute(
            select(Collection).where(Collection.idno == idno, Collection.id != col_id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="ID-Nr. bereits vergeben.")

    await _validate_parent_id(db, col_id, data.parent_id)

    collection_type = normalize_subtype_name(
        data.collection_type,
        allow_null=True,
    )
    await ensure_subtype_exists(db, "collection", collection_type)
    metadata = await prepare_metadata(
        db, "collection", data.metadata_, collection_type, existing=col.metadata_,
        can_edit_locked=current_user.role in {"admin", "superuser"},
    )
    errors = await validate_metadata(
        db, "collection", metadata, collection_type, skip_required=data.status == "draft"
    )
    if errors:
        raise HTTPException(status_code=422, detail=errors)

    old = {
        "idno": col.idno,
        "collection_type": col.collection_type,
        "parent_id": str(col.parent_id) if col.parent_id else None,
        "status": col.status,
        "metadata": col.metadata_,
    }
    col.idno = idno
    col.collection_type = collection_type
    col.parent_id = data.parent_id
    col.status = data.status
    col.metadata_ = metadata

    await flush_record(db, col)
    await sync_schema_relations(db, "collection", col.id, metadata)
    col_diff = diff_fields(
        old,
        {
            "idno": idno,
            "collection_type": collection_type,
            "parent_id": str(data.parent_id) if data.parent_id else None,
            "status": data.status,
            "metadata": metadata,
        },
    )
    if col_diff:
        await log_change(
            db,
            record_type="collection",
            record_id=col.id,
            user_id=current_user.id,
            action="update",
            changed_fields=col_diff,
        )
    if (
        old["status"] not in PUBLIC_SAVE_STATUSES
        and data.status in PUBLIC_SAVE_STATUSES
    ):
        try:
            await pid_service.ensure_pids_on_publish(db, "collection", col, current_user.id)
        except pid_service.PidMintError as exc:
            raise HTTPException(status_code=422, detail=f"PID-Vergabe fehlgeschlagen: {exc}") from exc
    try:
        await search_service.index_record("collection", col, db)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    return col


@router.post(
    "/{col_id}/publish",
    summary="Publish a collection after validating required fields",
    responses={
        403: {"description": "Insufficient permissions"},
    },
)
async def publish_collection(
    col_id: uuid.UUID,
    db: DBDep,
    current_user: User = require_record_permission("collection", "update"),
) -> dict[str, Any]:
    """Publish a collection after validating required fields."""
    ok, errors = await can_publish(db, "collection", str(col_id))
    if not ok:
        raise HTTPException(status_code=422, detail={"errors": errors})
    result = await publish_record(db, "collection", str(col_id), str(current_user.id))
    if not result.get("ok"):
        raise HTTPException(status_code=422, detail={"errors": result.get("errors", [])})
    await db.commit()
    return result


@router.delete(
    "/{col_id}",
    status_code=204,
    summary="Delete a collection record",
    responses={
        404: {"description": "Collection not found"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Record has linked relations (pass force=true to delete anyway)"},
    },
)
async def delete_collection(
    col_id: uuid.UUID,
    db: DBDep,
    current_user: User = require_record_permission("collection", "delete"),
    force: bool = Query(False),
) -> None:
    result = await db.execute(select(Collection).where(Collection.id == col_id))
    col = result.scalar_one_or_none()
    if not col:
        raise HTTPException(status_code=404, detail="Sammlung nicht gefunden")

    related_count = await count_relations(db, "collection", col_id)
    if related_count > 0 and not force:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": f"Dieser Datensatz ist mit {related_count} anderen Datensätzen verknüpft.",
                "related_count": related_count,
            },
        )

    col.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    await log_change(
        db,
        record_type="collection",
        record_id=col.id,
        user_id=current_user.id,
        action="delete",
        changed_fields=delete_label_fields(col.idno, col.metadata_),
    )
    await flush_record(db, col)
    try:
        await search_service.remove_record(col.id, record_type="collection")
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)

    from katalon.workers.cleanup_tasks import cleanup_relation_refs
    from katalon.workers.enqueue import enqueue

    enqueue(cleanup_relation_refs, "collection", str(col_id))


@router.post(
    "/{col_id}/restore",
    response_model=CollectionRead,
    summary="Restore a soft-deleted collection",
    responses={
        404: {"description": "Collection not found or not deleted"},
        403: {"description": "Insufficient permissions"},
    },
)
async def restore_collection(
    col_id: uuid.UUID,
    db: DBDep,
    current_user: User = require_role("admin"),
) -> Collection:
    result = await db.execute(select(Collection).where(Collection.id == col_id))
    col = result.scalar_one_or_none()
    if not col or col.deleted_at is None:
        raise HTTPException(status_code=404, detail="Sammlung nicht gefunden")
    col.deleted_at = None
    await log_change(
        db,
        record_type="collection",
        record_id=col.id,
        user_id=current_user.id,
        action="undelete",
    )
    await flush_record(db, col)
    try:
        await search_service.index_record("collection", col, db)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    return col


@router.get(
    "/trash/list",
    response_model=list[CollectionRead],
    summary="List soft-deleted collections",
)
async def list_deleted_collections(
    db: DBDep, current_user: User = require_role("admin")
) -> list[Collection]:
    result = await db.execute(
        select(Collection)
        .where(Collection.deleted_at.is_not(None))
        .order_by(Collection.deleted_at.desc())
    )
    return list(result.scalars().all())


@router.post(
    "/{col_id}/snapshots",
    response_model=SnapshotRead,
    status_code=201,
    summary="Create a snapshot of the current collection state",
    responses={
        404: {"description": "Collection not found"},
        403: {"description": "Insufficient permissions"},
    },
)
async def create_snapshot(
    col_id: uuid.UUID,
    data: SnapshotCreate,
    db: DBDep,
    current_user: User = require_record_permission("collection", "update"),
) -> RecordSnapshot:
    result = await db.execute(select(Collection).where(Collection.id == col_id))
    col = result.scalar_one_or_none()
    if not col:
        raise HTTPException(status_code=404, detail="Sammlung nicht gefunden")
    snap = RecordSnapshot(
        record_type="collection",
        record_id=col.id,
        label=data.label,
        snapshot={
            "idno": col.idno,
            "collection_type": col.collection_type,
            "parent_id": str(col.parent_id) if col.parent_id else None,
            "status": col.status,
            "metadata": col.metadata_,
        },
        created_by=current_user.id,
    )
    db.add(snap)
    await db.flush()
    return snap


@router.get(
    "/{col_id}/snapshots",
    response_model=list[SnapshotRead],
    summary="List snapshots for a collection",
)
async def list_snapshots(col_id: uuid.UUID, db: DBDep) -> list[RecordSnapshot]:
    result = await db.execute(
        select(RecordSnapshot)
        .where(RecordSnapshot.record_type == "collection", RecordSnapshot.record_id == col_id)
        .order_by(RecordSnapshot.created_at.desc())
    )
    return list(result.scalars().all())


@router.post(
    "/{col_id}/snapshots/{snapshot_id}/restore",
    response_model=CollectionRead,
    summary="Restore a collection from a snapshot",
    responses={
        404: {"description": "Collection or snapshot not found"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Version conflict"},
        428: {"description": "If-Match header required"},
    },
)
async def restore_snapshot(
    col_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    db: DBDep,
    current_user: User = require_record_permission("collection", "update"),
    if_match: int | None = Header(None, alias="If-Match"),
) -> Collection:
    snap_result = await db.execute(
        select(RecordSnapshot).where(
            RecordSnapshot.id == snapshot_id,
            RecordSnapshot.record_type == "collection",
            RecordSnapshot.record_id == col_id,
        )
    )
    snap = snap_result.scalar_one_or_none()
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot nicht gefunden")

    col_result = await db.execute(select(Collection).where(Collection.id == col_id))
    col = col_result.scalar_one_or_none()
    if not col:
        raise HTTPException(status_code=404, detail="Sammlung nicht gefunden")
    require_version(col.version, if_match)

    data = snap.snapshot
    if "idno" in data:
        col.idno = data["idno"]
    if "collection_type" in data:
        col.collection_type = data["collection_type"]
    if "parent_id" in data:
        col.parent_id = uuid.UUID(data["parent_id"]) if data["parent_id"] else None
    if "status" in data:
        col.status = data["status"]
    if "metadata" in data:
        col.metadata_ = data["metadata"]
    flag_modified(col, "metadata_")
    await flush_record(db, col)
    await sync_schema_relations(db, "collection", col.id, col.metadata_)
    await log_change(
        db,
        record_type="collection",
        record_id=col.id,
        user_id=current_user.id,
        action="restore",
        changed_fields={"snapshot_id": str(snapshot_id)},
    )
    await db.commit()
    try:
        await search_service.index_record("collection", col, db)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    return col


@router.get(
    "/{col_id}/audit-log",
    response_model=list[AuditLogRead],
    summary="List audit log entries for a collection",
)
async def list_collection_audit_log(col_id: uuid.UUID, db: DBDep) -> list[AuditLogRead]:
    from katalon.api.v1.audit import list_audit_log

    return await list_audit_log(db, record_type="collection", record_id=col_id, limit=100)
