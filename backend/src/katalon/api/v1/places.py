# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm.attributes import flag_modified

from katalon.config import settings
from katalon.core.concurrency import flush_record, require_version
from katalon.core.dependencies import (
    DBDep,
    OptionalCurrentUser,
    has_record_permission,
    require_record_permission,
    require_role,
)
from katalon.core.limiter import limiter
from katalon.core.list_query import SortBy, SortDir, apply_sort
from katalon.core.models import AdminConfig, Place, RecordSnapshot, User
from katalon.core.schemas import AuditLogRead, PlaceCreate, PlaceRead, SnapshotCreate, SnapshotRead
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
from katalon.services.lock_service import enforce_not_locked
from katalon.services.place_service import (
    count_direct_children,
    find_cycle_or_missing_parent,
    get_place_subtree_ids,
    reparent_children,
)
from katalon.services.presence_service import enforce_not_blocked
from katalon.services.public_metadata_service import metadata_text_clause, project_public_record
from katalon.services.publish_service import can_publish, publish_record
from katalon.services.relation_service import count_relations, sync_schema_relations
from katalon.services.schema_service import prepare_metadata, validate_metadata
from katalon.services.subtype_service import (
    ensure_subtype_exists,
    normalize_subtype_name,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/places", tags=["places"])
#: Statuses that make a record publicly visible and trigger PID auto-minting.
PUBLIC_SAVE_STATUSES = set(PUBLIC_STATUSES)


async def _visibility_user(db: DBDep, user: OptionalCurrentUser) -> User | None:
    return user if user and await has_record_permission(db, user, "place", "read") else None


@router.get(
    "",
    response_model=dict[str, Any],
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
    parent_id: uuid.UUID | None = None,
    root: bool = False,
    sort_by: SortBy | None = None,
    sort_dir: SortDir = "desc",
) -> dict[str, Any]:
    query = select(Place)
    if parent_id is not None:
        query = query.where(Place.parent_id == parent_id)
    elif root:
        query = query.where(Place.parent_id.is_(None))
    if place_type:
        query = query.where(Place.place_type == place_type)
    if status:
        query = query.where(Place.status == status)
    visibility_user = await _visibility_user(db, current_user)
    query = apply_public_visibility(query, Place, visibility_user)
    if q:
        query = query.where(
            Place.idno.icontains(q, autoescape=True)
            | await metadata_text_clause(db, Place, "place", q, visibility_user)
        )
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    query = apply_sort(
        query.offset((page - 1) * page_size).limit(page_size), Place, sort_by, sort_dir
    )
    items = (await db.execute(query)).scalars().all()
    response_items = [PlaceRead.model_validate(i) for i in items]
    if visibility_user is None:
        response_items = [
            await project_public_record(db, item, "place", place.place_type)
            for item, place in zip(response_items, items, strict=True)
        ]
    return {"total": total, "page": page, "page_size": page_size, "items": response_items}


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
async def create_place(
    data: PlaceCreate, db: DBDep, current_user: User = require_record_permission("place", "create")
) -> Place:
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
            raise HTTPException(
                status_code=422, detail=f"ID-Nr. entspricht nicht dem Muster: {pattern}"
            )
        if schema:
            await maybe_advance_counter(db, "place", schema, idno)

    place_type = normalize_subtype_name(
        data.place_type,
        allow_null=True,
    )
    await ensure_subtype_exists(db, "place", place_type)
    metadata = await prepare_metadata(
        db,
        "place",
        data.metadata_,
        place_type,
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
    parent_error = await find_cycle_or_missing_parent(db, None, data.parent_id)
    if parent_error:
        raise HTTPException(status_code=422, detail=parent_error)
    place = Place(
        idno=idno,
        place_type=place_type,
        parent_id=data.parent_id,
        status=data.status,
        metadata_=metadata,
        ai_provenance=data.ai_provenance,
    )
    if data.lat is not None and data.lon is not None:
        from geoalchemy2.elements import WKTElement

        place.geom = WKTElement(f"POINT({data.lon} {data.lat})", srid=4326)
    db.add(place)
    await flush_record(db, place)
    await sync_schema_relations(db, "place", place.id, metadata)
    await db.flush()
    await log_change(
        db, record_type="place", record_id=place.id, user_id=current_user.id, action="create"
    )
    if data.status in PUBLIC_SAVE_STATUSES:
        try:
            await pid_service.ensure_pids_on_publish(db, "place", place, current_user.id)
        except pid_service.PidMintError as exc:
            raise HTTPException(
                status_code=422, detail=f"PID-Vergabe fehlgeschlagen: {exc}"
            ) from exc
    try:
        await search_service.index_record("place", place, db)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    return place


@router.get(
    "/{place_id}/export",
    summary="Export a single place record as JSON-LD or Turtle RDF",
)
@limiter.limit(lambda: settings.rate_limit_public_export)
async def export_place(
    place_id: uuid.UUID,
    db: DBDep,
    request: Request,
    current_user: OptionalCurrentUser,
    format: str | None = Query(None),
    accept: str | None = Header(None),
) -> Response:
    from katalon.services.rdf_service import handle_single_record_export

    return await handle_single_record_export(
        "place",
        place_id,
        db,
        request,
        current_user=current_user,
        format_param=format,
        accept_header=accept,
    )


@router.get(
    "/{place_id}",
    response_model=PlaceRead,
    summary="Get a single place by ID",
    responses={
        404: {"description": "Place not found"},
    },
)
async def get_place(
    place_id: uuid.UUID,
    db: DBDep,
    current_user: OptionalCurrentUser,
    request: Request = None,  # type: ignore[assignment]
    format: str | None = Query(None),
    accept: str | None = Header(None),
) -> Any:
    is_rdf_format = isinstance(format, str) and format.lower() in (
        "jsonld",
        "json-ld",
        "ttl",
        "turtle",
    )
    is_rdf_accept = isinstance(accept, str) and (
        "application/ld+json" in accept or "text/turtle" in accept
    )
    if is_rdf_format or is_rdf_accept:
        from katalon.services.rdf_service import handle_single_record_export

        return await handle_single_record_export(
            "place",
            place_id,
            db,
            request,
            current_user=current_user,
            format_param=format if isinstance(format, str) else None,
            accept_header=accept if isinstance(accept, str) else None,
        )

    result = await db.execute(select(Place).where(Place.id == place_id))
    place = result.scalar_one_or_none()
    if not place:
        raise HTTPException(status_code=404, detail="Ort nicht gefunden")
    visibility_user = await _visibility_user(db, current_user)
    ensure_publicly_visible(place, visibility_user, "Ort nicht gefunden")
    if visibility_user is None:
        return await project_public_record(
            db, PlaceRead.model_validate(place), "place", place.place_type
        )
    return place


@router.put(
    "/{place_id}",
    response_model=PlaceRead,
    summary="Update a place record",
    responses={
        404: {"description": "Place not found"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Version conflict (If-Match mismatch)"},
        428: {"description": "If-Match header required"},
        400: {"description": "Idno already taken"},
        422: {"description": "Idno missing or metadata validation failed"},
    },
)
async def update_place(
    place_id: uuid.UUID,
    data: PlaceCreate,
    db: DBDep,
    current_user: User = require_record_permission("place", "update"),
    if_match: int | None = Header(None, alias="If-Match"),
) -> Place:
    result = await db.execute(select(Place).where(Place.id == place_id))
    place = result.scalar_one_or_none()
    if not place:
        raise HTTPException(status_code=404, detail="Ort nicht gefunden")
    require_version(place.version, if_match)
    await enforce_not_blocked(db, "place", place.id, current_user)
    await enforce_not_locked(db, "place", place.id, current_user)
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
    place_type = normalize_subtype_name(
        data.place_type,
        allow_null=True,
    )
    await ensure_subtype_exists(db, "place", place_type)
    metadata = await prepare_metadata(
        db,
        "place",
        data.metadata_,
        place_type,
        existing=place.metadata_,
        can_edit_locked=current_user.role in {"admin", "superuser"},
    )
    errors = await validate_metadata(
        db,
        "place",
        metadata,
        place_type,
        existing=place.metadata_,
        skip_required=data.status == "draft",
        record_id=place_id,
    )
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    parent_error = await find_cycle_or_missing_parent(db, place_id, data.parent_id)
    if parent_error:
        raise HTTPException(status_code=422, detail=parent_error)
    old = {
        "idno": place.idno,
        "place_type": place.place_type,
        "parent_id": str(place.parent_id) if place.parent_id else None,
        "status": place.status,
        "metadata": place.metadata_,
    }
    place.idno = idno
    place.place_type = place_type
    place.parent_id = data.parent_id
    place.status = data.status
    place.metadata_ = metadata
    place.ai_provenance = data.ai_provenance
    if data.lat is not None and data.lon is not None:
        from geoalchemy2.elements import WKTElement

        place.geom = WKTElement(f"POINT({data.lon} {data.lat})", srid=4326)

    await flush_record(db, place)
    await sync_schema_relations(db, "place", place.id, metadata)
    place_diff = diff_fields(
        old,
        {
            "idno": idno,
            "place_type": place_type,
            "parent_id": str(data.parent_id) if data.parent_id else None,
            "status": data.status,
            "metadata": metadata,
        },
    )
    if place_diff:
        await log_change(
            db,
            record_type="place",
            record_id=place.id,
            user_id=current_user.id,
            action="update",
            changed_fields=place_diff,
        )
    if old["status"] not in PUBLIC_SAVE_STATUSES and data.status in PUBLIC_SAVE_STATUSES:
        try:
            await pid_service.ensure_pids_on_publish(db, "place", place, current_user.id)
        except pid_service.PidMintError as exc:
            raise HTTPException(
                status_code=422, detail=f"PID-Vergabe fehlgeschlagen: {exc}"
            ) from exc
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
    current_user: User = require_record_permission("place", "update"),
) -> dict[str, Any]:
    """Publish a place after validating required fields."""
    ok, errors = await can_publish(db, "place", str(place_id))
    if not ok:
        raise HTTPException(status_code=422, detail={"errors": errors})
    result = await publish_record(db, "place", str(place_id), str(current_user.id))
    if not result.get("ok"):
        raise HTTPException(status_code=422, detail={"errors": result.get("errors", [])})
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
    current_user: User = require_record_permission("place", "delete"),
    force: bool = Query(False),
    cascade: bool = Query(False, description="Delete this place and its whole subtree."),
    reparent: bool = Query(
        False, description="Move direct children up to this place's parent before deleting."
    ),
) -> None:
    result = await db.execute(select(Place).where(Place.id == place_id))
    place = result.scalar_one_or_none()
    if not place:
        raise HTTPException(status_code=404, detail="Ort nicht gefunden")
    if cascade and reparent:
        raise HTTPException(
            status_code=400, detail="cascade und reparent schließen sich gegenseitig aus."
        )

    child_count = await count_direct_children(db, place_id)
    if child_count > 0 and not cascade and not reparent:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": f"Dieser Ort hat {child_count} untergeordnete Orte.",
                "child_count": child_count,
            },
        )

    target_ids = [place_id]
    if cascade and child_count > 0:
        target_ids = await get_place_subtree_ids(db, place_id)
    elif reparent and child_count > 0:
        await reparent_children(db, place_id, place.parent_id)

    related_count = sum([await count_relations(db, "place", tid) for tid in target_ids])
    if related_count > 0 and not force:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": f"{len(target_ids)} betroffene Orte sind mit insgesamt "
                f"{related_count} anderen Datensätzen verknüpft.",
                "related_count": related_count,
            },
        )

    targets = (
        (await db.execute(select(Place).where(Place.id.in_(target_ids)))).scalars().all()
    )
    now = datetime.now(UTC).replace(tzinfo=None)
    for rec in targets:
        rec.deleted_at = now
        await log_change(
            db,
            record_type="place",
            record_id=rec.id,
            user_id=current_user.id,
            action="delete",
            changed_fields=delete_label_fields(rec.idno, rec.metadata_),
        )
    await flush_record(db, place)
    for rec in targets:
        try:
            await search_service.remove_record(rec.id, db, record_type="place")
        except Exception:
            logger.warning("ES index/remove failed", exc_info=True)


@router.post(
    "/{place_id}/restore",
    response_model=PlaceRead,
    summary="Restore a soft-deleted place",
    responses={
        404: {"description": "Place not found or not deleted"},
        403: {"description": "Insufficient permissions"},
    },
)
async def restore_place(
    place_id: uuid.UUID,
    db: DBDep,
    current_user: User = require_role("admin"),
) -> Place:
    result = await db.execute(select(Place).where(Place.id == place_id))
    place = result.scalar_one_or_none()
    if not place or place.deleted_at is None:
        raise HTTPException(status_code=404, detail="Ort nicht gefunden")
    place.deleted_at = None
    await log_change(
        db, record_type="place", record_id=place.id, user_id=current_user.id, action="undelete"
    )
    await flush_record(db, place)
    try:
        await search_service.index_record("place", place, db)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    return place


@router.get(
    "/trash/list",
    response_model=list[PlaceRead],
    summary="List soft-deleted places",
)
async def list_deleted_places(db: DBDep, current_user: User = require_role("admin")) -> list[Place]:
    result = await db.execute(
        select(Place).where(Place.deleted_at.is_not(None)).order_by(Place.deleted_at.desc())
    )
    return list(result.scalars().all())


@router.post(
    "/{place_id}/purge",
    status_code=204,
    summary="Permanently delete a soft-deleted place (hard delete)",
    responses={
        404: {"description": "Place not found or not in trash"},
        403: {"description": "Insufficient permissions"},
    },
)
async def purge_place(
    place_id: uuid.UUID,
    db: DBDep,
    current_user: User = require_role("admin"),
) -> None:
    from katalon.workers.purge_tasks import purge_record_now

    ok = await purge_record_now(db, "place", place_id, current_user.id)
    if not ok:
        raise HTTPException(
            status_code=404, detail="Ort nicht gefunden oder nicht im Papierkorb"
        )


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
    place_id: uuid.UUID,
    data: SnapshotCreate,
    db: DBDep,
    current_user: User = require_record_permission("place", "update"),
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
async def list_snapshots(
    place_id: uuid.UUID,
    db: DBDep,
    _: User = require_record_permission("place", "read"),
) -> list[RecordSnapshot]:
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
    current_user: User = require_record_permission("place", "update"),
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
async def list_place_audit_log(
    place_id: uuid.UUID,
    db: DBDep,
    current_user: User = require_record_permission("place", "read"),
) -> list[AuditLogRead]:
    from katalon.api.v1.audit import list_audit_log

    return await list_audit_log(
        db, current_user=current_user, record_type="place", record_id=place_id, limit=100
    )
