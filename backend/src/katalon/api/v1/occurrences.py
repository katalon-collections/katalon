# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from sqlalchemy import Text, cast, func, select
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
from katalon.core.models import AdminConfig, Occurrence, RecordSnapshot, User
from katalon.core.schemas import (
    AuditLogRead,
    OccurrenceCreate,
    OccurrenceRead,
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
from katalon.services.lock_service import enforce_not_locked
from katalon.services.presence_service import enforce_not_blocked
from katalon.services.public_metadata_service import project_public_record
from katalon.services.publish_service import can_publish, publish_record
from katalon.services.relation_service import count_relations, sync_schema_relations
from katalon.services.schema_service import prepare_metadata, validate_metadata
from katalon.services.subtype_service import (
    ensure_subtype_exists,
    normalize_subtype_name,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/occurrences", tags=["occurrences"])
#: Statuses that make a record publicly visible and trigger PID auto-minting.
PUBLIC_SAVE_STATUSES = set(PUBLIC_STATUSES)


async def _visibility_user(db: DBDep, user: OptionalCurrentUser) -> User | None:
    return user if user and await has_record_permission(db, user, "occurrence", "read") else None


@router.get(
    "",
    response_model=dict[str, Any],
    summary="List occurrences with pagination and filters",
)
async def list_occurrences(
    db: DBDep,
    current_user: OptionalCurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    occurrence_type: str | None = None,
    status: str | None = None,
    q: str | None = None,
    sort_by: SortBy | None = None,
    sort_dir: SortDir = "desc",
) -> dict[str, Any]:
    query = select(Occurrence)
    if occurrence_type:
        query = query.where(Occurrence.occurrence_type == occurrence_type)
    if status:
        query = query.where(Occurrence.status == status)
    visibility_user = await _visibility_user(db, current_user)
    query = apply_public_visibility(query, Occurrence, visibility_user)
    if q:
        query = query.where(
            Occurrence.idno.icontains(q, autoescape=True)
            | cast(Occurrence.metadata_, Text).icontains(q, autoescape=True)
        )
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    query = apply_sort(query.offset((page - 1) * page_size).limit(page_size), Occurrence, sort_by, sort_dir)
    items = (await db.execute(query)).scalars().all()
    response_items = [OccurrenceRead.model_validate(i) for i in items]
    if visibility_user is None:
        response_items = [
            await project_public_record(db, item, "occurrence", occurrence.occurrence_type)
            for item, occurrence in zip(response_items, items, strict=True)
        ]
    return {"total": total, "page": page, "page_size": page_size, "items": response_items}


@router.post(
    "",
    response_model=OccurrenceRead,
    status_code=201,
    summary="Create a new occurrence record",
    responses={
        403: {"description": "Insufficient permissions"},
        400: {"description": "Idno already taken"},
        422: {"description": "Idno missing/invalid pattern or metadata validation failed"},
    },
)
async def create_occurrence(data: OccurrenceCreate, db: DBDep, current_user: User = require_record_permission("occurrence", "create")) -> Occurrence:
    cfg_result = await db.execute(select(AdminConfig).where(AdminConfig.key == "default"))
    cfg = cfg_result.scalar_one_or_none()
    schema = (cfg.idno_schemas or {}).get("occurrence") if cfg else None
    pattern = (cfg.idno_patterns or {}).get("occurrence") if cfg else None

    if not data.idno or not data.idno.strip():
        if schema:
            idno = await consume_next_idno(db, "occurrence", schema)
        elif data.status == "draft":
            idno = None
        else:
            raise HTTPException(status_code=422, detail="ID-Nr. ist ein Pflichtfeld.")
    else:
        idno = data.idno.strip()
        if pattern and not validate_idno_pattern(pattern, idno):
            raise HTTPException(status_code=422, detail=f"ID-Nr. entspricht nicht dem Muster: {pattern}")
        if schema:
            await maybe_advance_counter(db, "occurrence", schema, idno)

    occurrence_type = normalize_subtype_name(
        data.occurrence_type,
        allow_null=True,
    )
    await ensure_subtype_exists(db, "occurrence", occurrence_type)
    metadata = await prepare_metadata(
        db, "occurrence", data.metadata_, occurrence_type,
        can_edit_locked=current_user.role in {"admin", "superuser"},
    )
    errors = await validate_metadata(
        db, "occurrence", metadata, occurrence_type, skip_required=data.status == "draft"
    )
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    if idno is not None:
        existing = await db.execute(select(Occurrence).where(Occurrence.idno == idno))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="ID-Nr. bereits vergeben.")
    occ = Occurrence(idno=idno, occurrence_type=occurrence_type, status=data.status, metadata_=metadata)
    db.add(occ)
    await flush_record(db, occ)
    await sync_schema_relations(db, "occurrence", occ.id, metadata)
    await db.flush()
    await log_change(db, record_type="occurrence", record_id=occ.id, user_id=current_user.id, action="create")
    if data.status in PUBLIC_SAVE_STATUSES:
        try:
            await pid_service.ensure_pids_on_publish(db, "occurrence", occ, current_user.id)
        except pid_service.PidMintError as exc:
            raise HTTPException(status_code=422, detail=f"PID-Vergabe fehlgeschlagen: {exc}") from exc
    try:
        await search_service.index_record("occurrence", occ, db)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    return occ


@router.get(
    "/{occ_id}/export",
    summary="Export a single occurrence record as JSON-LD or Turtle RDF",
)
@limiter.limit(lambda: settings.rate_limit_public_export)
async def export_occurrence(
    occ_id: uuid.UUID,
    db: DBDep,
    request: Request,
    current_user: OptionalCurrentUser,
    format: str | None = Query(None),
    accept: str | None = Header(None),
) -> Response:
    from katalon.services.rdf_service import handle_single_record_export

    return await handle_single_record_export(
        "occurrence",
        occ_id,
        db,
        request,
        current_user=current_user,
        format_param=format,
        accept_header=accept,
    )


@router.get(
    "/{occ_id}",
    response_model=OccurrenceRead,
    summary="Get a single occurrence by ID",
    responses={
        404: {"description": "Occurrence not found"},
    },
)
async def get_occurrence(
    occ_id: uuid.UUID,
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
            "occurrence",
            occ_id,
            db,
            request,
            current_user=current_user,
            format_param=format if isinstance(format, str) else None,
            accept_header=accept if isinstance(accept, str) else None,
        )

    result = await db.execute(select(Occurrence).where(Occurrence.id == occ_id))
    occ = result.scalar_one_or_none()
    if not occ:
        raise HTTPException(status_code=404, detail="Occurrence nicht gefunden")
    visibility_user = await _visibility_user(db, current_user)
    ensure_publicly_visible(occ, visibility_user, "Occurrence nicht gefunden")
    if visibility_user is None:
        return await project_public_record(db, OccurrenceRead.model_validate(occ), "occurrence", occ.occurrence_type)
    return occ

@router.put(
    "/{occ_id}",
    response_model=OccurrenceRead,
    summary="Update an occurrence record",
    responses={
        404: {"description": "Occurrence not found"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Version conflict (If-Match mismatch)"},
        400: {"description": "Idno already taken"},
        422: {"description": "Idno missing or metadata validation failed"},
    },
)
async def update_occurrence(
    occ_id: uuid.UUID,
    data: OccurrenceCreate,
    db: DBDep,
    current_user: User = require_record_permission("occurrence", "update"),
    if_match: int | None = Header(None, alias="If-Match"),
) -> Occurrence:
    result = await db.execute(select(Occurrence).where(Occurrence.id == occ_id))
    occ = result.scalar_one_or_none()
    if not occ:
        raise HTTPException(status_code=404, detail="Occurrence nicht gefunden")
    check_version(occ.version, if_match)
    await enforce_not_blocked(db, "occurrence", occ.id, current_user)
    await enforce_not_locked(db, "occurrence", occ.id, current_user)
    if not data.idno or not data.idno.strip():
        if data.status == "draft":
            idno = None
        else:
            raise HTTPException(status_code=422, detail="ID-Nr. ist ein Pflichtfeld.")
    else:
        idno = data.idno.strip()
        existing = await db.execute(select(Occurrence).where(Occurrence.idno == idno, Occurrence.id != occ_id))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="ID-Nr. bereits vergeben.")
    occurrence_type = normalize_subtype_name(
        data.occurrence_type,
        allow_null=True,
    )
    await ensure_subtype_exists(db, "occurrence", occurrence_type)
    metadata = await prepare_metadata(
        db, "occurrence", data.metadata_, occurrence_type, existing=occ.metadata_,
        can_edit_locked=current_user.role in {"admin", "superuser"},
    )
    errors = await validate_metadata(
        db, "occurrence", metadata, occurrence_type, skip_required=data.status == "draft"
    )
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    old = {
        "idno": occ.idno,
        "occurrence_type": occ.occurrence_type,
        "status": occ.status,
        "metadata": occ.metadata_,
    }
    occ.idno = idno
    occ.occurrence_type = occurrence_type
    occ.status = data.status
    occ.metadata_ = metadata

    await flush_record(db, occ)
    await sync_schema_relations(db, "occurrence", occ.id, metadata)
    occ_diff = diff_fields(old, {"idno": idno, "occurrence_type": occurrence_type, "status": data.status, "metadata": metadata})
    if occ_diff:
        await log_change(db, record_type="occurrence", record_id=occ.id, user_id=current_user.id, action="update",
                         changed_fields=occ_diff)
    if (
        old["status"] not in PUBLIC_SAVE_STATUSES
        and data.status in PUBLIC_SAVE_STATUSES
    ):
        try:
            await pid_service.ensure_pids_on_publish(db, "occurrence", occ, current_user.id)
        except pid_service.PidMintError as exc:
            raise HTTPException(status_code=422, detail=f"PID-Vergabe fehlgeschlagen: {exc}") from exc
    try:
        await search_service.index_record("occurrence", occ, db)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    return occ


@router.post(
    "/{occ_id}/publish",
    summary="Publish an occurrence after validating required fields",
    responses={
        403: {"description": "Insufficient permissions"},
    },
)
async def publish_occurrence(
    occ_id: uuid.UUID,
    db: DBDep,
    current_user: User = require_record_permission("occurrence", "update"),
) -> dict[str, Any]:
    """Publish an occurrence after validating required fields."""
    ok, errors = await can_publish(db, "occurrence", str(occ_id))
    if not ok:
        raise HTTPException(status_code=422, detail={"errors": errors})
    result = await publish_record(db, "occurrence", str(occ_id), str(current_user.id))
    if not result.get("ok"):
        raise HTTPException(status_code=422, detail={"errors": result.get("errors", [])})
    await db.commit()
    return result


@router.delete(
    "/{occ_id}",
    status_code=204,
    summary="Delete an occurrence record",
    responses={
        404: {"description": "Occurrence not found"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Record has linked relations (pass force=true to delete anyway)"},
    },
)
async def delete_occurrence(
    occ_id: uuid.UUID,
    db: DBDep,
    current_user: User = require_record_permission("occurrence", "delete"),
    force: bool = Query(False),
) -> None:
    result = await db.execute(select(Occurrence).where(Occurrence.id == occ_id))
    occ = result.scalar_one_or_none()
    if not occ:
        raise HTTPException(status_code=404, detail="Occurrence nicht gefunden")

    related_count = await count_relations(db, "occurrence", occ_id)
    if related_count > 0 and not force:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": f"Dieser Datensatz ist mit {related_count} anderen Datensätzen verknüpft.",
                "related_count": related_count,
            },
        )

    occ.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    await log_change(
        db, record_type="occurrence", record_id=occ.id, user_id=current_user.id, action="delete",
        changed_fields=delete_label_fields(occ.idno, occ.metadata_),
    )
    await flush_record(db, occ)
    try:
        await search_service.remove_record(occ.id, record_type="occurrence")
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)

    from katalon.workers.cleanup_tasks import cleanup_relation_refs
    from katalon.workers.enqueue import enqueue
    enqueue(cleanup_relation_refs, "occurrence", str(occ_id))


@router.post(
    "/{occ_id}/restore",
    response_model=OccurrenceRead,
    summary="Restore a soft-deleted occurrence",
    responses={
        404: {"description": "Occurrence not found or not deleted"},
        403: {"description": "Insufficient permissions"},
    },
)
async def restore_occurrence(
    occ_id: uuid.UUID,
    db: DBDep,
    current_user: User = require_role("admin"),
) -> Occurrence:
    result = await db.execute(select(Occurrence).where(Occurrence.id == occ_id))
    occ = result.scalar_one_or_none()
    if not occ or occ.deleted_at is None:
        raise HTTPException(status_code=404, detail="Occurrence nicht gefunden")
    occ.deleted_at = None
    await log_change(db, record_type="occurrence", record_id=occ.id, user_id=current_user.id, action="undelete")
    await flush_record(db, occ)
    try:
        await search_service.index_record("occurrence", occ, db)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    return occ


@router.get(
    "/trash/list",
    response_model=list[OccurrenceRead],
    summary="List soft-deleted occurrences",
)
async def list_deleted_occurrences(db: DBDep, current_user: User = require_role("admin")) -> list[Occurrence]:
    result = await db.execute(
        select(Occurrence).where(Occurrence.deleted_at.is_not(None)).order_by(Occurrence.deleted_at.desc())
    )
    return list(result.scalars().all())


@router.post(
    "/{occ_id}/snapshots",
    response_model=SnapshotRead,
    status_code=201,
    summary="Create a snapshot of the current occurrence state",
    responses={
        404: {"description": "Occurrence not found"},
        403: {"description": "Insufficient permissions"},
    },
)
async def create_snapshot(
    occ_id: uuid.UUID, data: SnapshotCreate, db: DBDep, current_user: User = require_record_permission("occurrence", "update")
) -> RecordSnapshot:
    result = await db.execute(select(Occurrence).where(Occurrence.id == occ_id))
    occ = result.scalar_one_or_none()
    if not occ:
        raise HTTPException(status_code=404, detail="Occurrence nicht gefunden")
    snap = RecordSnapshot(
        record_type="occurrence",
        record_id=occ.id,
        label=data.label,
        snapshot={
            "idno": occ.idno,
            "occurrence_type": occ.occurrence_type,
            "status": occ.status,
            "metadata": occ.metadata_,
        },
        created_by=current_user.id,
    )
    db.add(snap)
    await db.flush()
    return snap


@router.get(
    "/{occ_id}/snapshots",
    response_model=list[SnapshotRead],
    summary="List snapshots for an occurrence",
)
async def list_snapshots(occ_id: uuid.UUID, db: DBDep) -> list[RecordSnapshot]:
    result = await db.execute(
        select(RecordSnapshot)
        .where(RecordSnapshot.record_type == "occurrence", RecordSnapshot.record_id == occ_id)
        .order_by(RecordSnapshot.created_at.desc())
    )
    return list(result.scalars().all())


@router.post(
    "/{occ_id}/snapshots/{snapshot_id}/restore",
    response_model=OccurrenceRead,
    summary="Restore an occurrence from a snapshot",
    responses={
        404: {"description": "Occurrence or snapshot not found"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Version conflict"},
        428: {"description": "If-Match header required"},
    },
)
async def restore_snapshot(
    occ_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    db: DBDep,
    current_user: User = require_record_permission("occurrence", "update"),
    if_match: int | None = Header(None, alias="If-Match"),
) -> Occurrence:
    snap_result = await db.execute(
        select(RecordSnapshot).where(
            RecordSnapshot.id == snapshot_id,
            RecordSnapshot.record_type == "occurrence",
            RecordSnapshot.record_id == occ_id,
        )
    )
    snap = snap_result.scalar_one_or_none()
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot nicht gefunden")

    occ_result = await db.execute(select(Occurrence).where(Occurrence.id == occ_id))
    occ = occ_result.scalar_one_or_none()
    if not occ:
        raise HTTPException(status_code=404, detail="Occurrence nicht gefunden")
    require_version(occ.version, if_match)

    data = snap.snapshot
    if "idno" in data:
        occ.idno = data["idno"]
    if "occurrence_type" in data:
        occ.occurrence_type = data["occurrence_type"]
    if "status" in data:
        occ.status = data["status"]
    if "metadata" in data:
        occ.metadata_ = data["metadata"]
    flag_modified(occ, "metadata_")
    await flush_record(db, occ)
    await sync_schema_relations(db, "occurrence", occ.id, occ.metadata_)
    await log_change(
        db,
        record_type="occurrence",
        record_id=occ.id,
        user_id=current_user.id,
        action="restore",
        changed_fields={"snapshot_id": str(snapshot_id)},
    )
    await db.commit()
    try:
        await search_service.index_record("occurrence", occ, db)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    return occ


@router.get(
    "/{occ_id}/audit-log",
    response_model=list[AuditLogRead],
    summary="List audit log entries for an occurrence",
)
async def list_occurrence_audit_log(occ_id: uuid.UUID, db: DBDep) -> list[AuditLogRead]:
    from katalon.api.v1.audit import list_audit_log
    return await list_audit_log(db, record_type="occurrence", record_id=occ_id, limit=100)
