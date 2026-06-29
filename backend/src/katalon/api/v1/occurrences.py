import logging
import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from katalon.core.dependencies import DBDep, OptionalCurrentUser, require_admin_or_editor
from katalon.core.models import AdminConfig, Occurrence, RecordSnapshot
from katalon.core.schemas import (
    AuditLogRead,
    OccurrenceCreate,
    OccurrenceRead,
    SnapshotCreate,
    SnapshotRead,
)
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

router = APIRouter(prefix="/occurrences", tags=["occurrences"])


@router.get("", response_model=dict)
async def list_occurrences(
    db: DBDep,
    current_user: OptionalCurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    occurrence_type: str | None = None,
    status: str | None = None,
    q: str | None = None,
) -> dict:
    query = select(Occurrence)
    if occurrence_type:
        query = query.where(Occurrence.occurrence_type == occurrence_type)
    if status:
        query = query.where(Occurrence.status == status)
    query = apply_public_visibility(query, Occurrence, current_user)
    if q:
        query = query.where(Occurrence.search_vector.match(q))
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    query = query.offset((page - 1) * page_size).limit(page_size).order_by(Occurrence.updated_at.desc())
    items = (await db.execute(query)).scalars().all()
    return {"total": total, "page": page, "page_size": page_size,
            "items": [OccurrenceRead.model_validate(i) for i in items]}


@router.post("", response_model=OccurrenceRead, status_code=201)
async def create_occurrence(data: OccurrenceCreate, db: DBDep, current_user=require_admin_or_editor()) -> Occurrence:
    cfg_result = await db.execute(select(AdminConfig).where(AdminConfig.key == "default"))
    cfg = cfg_result.scalar_one_or_none()
    schema = (cfg.idno_schemas or {}).get("occurrence") if cfg else None
    pattern = (cfg.idno_patterns or {}).get("occurrence") if cfg else None

    if not data.idno or not data.idno.strip():
        if schema:
            idno = await consume_next_idno(db, "occurrence", schema)
        else:
            raise HTTPException(status_code=422, detail="ID-Nr. ist ein Pflichtfeld.")
    else:
        idno = data.idno.strip()
        if pattern and not validate_idno_pattern(pattern, idno):
            raise HTTPException(status_code=422, detail=f"ID-Nr. entspricht nicht dem Muster: {pattern}")
        if schema:
            await maybe_advance_counter(db, "occurrence", schema, idno)

    _has_subtypes = await has_any_subtypes(db, "occurrence")
    occurrence_type = normalize_subtype_name(data.occurrence_type, allow_null=not _has_subtypes)
    await ensure_subtype_exists(db, "occurrence", occurrence_type)
    metadata = await prepare_metadata(
        db, "occurrence", data.metadata_, occurrence_type,
        can_edit_locked=current_user.role in {"admin", "superuser"},
    )
    errors = await validate_metadata(db, "occurrence", metadata, occurrence_type)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    existing = await db.execute(select(Occurrence).where(Occurrence.idno == idno))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="ID-Nr. bereits vergeben.")
    occ = Occurrence(idno=idno, occurrence_type=occurrence_type, status=data.status, metadata_=metadata)
    db.add(occ)
    await db.flush()
    await sync_schema_relations(db, "occurrence", occ.id, metadata)
    await db.flush()
    await log_change(db, record_type="occurrence", record_id=occ.id, user_id=current_user.id, action="create")
    try:
        await search_service.index_record("occurrence", occ, db)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    return occ


@router.get("/{occ_id}", response_model=OccurrenceRead)
async def get_occurrence(occ_id: uuid.UUID, db: DBDep, current_user: OptionalCurrentUser) -> Occurrence:
    result = await db.execute(select(Occurrence).where(Occurrence.id == occ_id))
    occ = result.scalar_one_or_none()
    if not occ:
        raise HTTPException(status_code=404, detail="Occurrence nicht gefunden")
    ensure_publicly_visible(occ, current_user, "Occurrence nicht gefunden")
    return occ


@router.put("/{occ_id}", response_model=OccurrenceRead)
async def update_occurrence(
    occ_id: uuid.UUID, data: OccurrenceCreate, db: DBDep, current_user=require_admin_or_editor()
) -> Occurrence:
    if not data.idno or not data.idno.strip():
        raise HTTPException(status_code=422, detail="ID-Nr. ist ein Pflichtfeld.")
    result = await db.execute(select(Occurrence).where(Occurrence.id == occ_id))
    occ = result.scalar_one_or_none()
    if not occ:
        raise HTTPException(status_code=404, detail="Occurrence nicht gefunden")
    existing = await db.execute(select(Occurrence).where(Occurrence.idno == data.idno.strip(), Occurrence.id != occ_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="ID-Nr. bereits vergeben.")
    occurrence_type = normalize_subtype_name(data.occurrence_type, allow_null=False)
    await ensure_subtype_exists(db, "occurrence", occurrence_type)
    metadata = await prepare_metadata(
        db, "occurrence", data.metadata_, occurrence_type, existing=occ.metadata_,
        can_edit_locked=current_user.role in {"admin", "superuser"},
    )
    errors = await validate_metadata(db, "occurrence", metadata, occurrence_type)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    old = {
        "idno": occ.idno,
        "occurrence_type": occ.occurrence_type,
        "status": occ.status,
        "metadata": occ.metadata_,
    }
    occ.idno = data.idno.strip()
    occ.occurrence_type = occurrence_type
    occ.status = data.status
    occ.metadata_ = metadata
    await sync_schema_relations(db, "occurrence", occ.id, metadata)
    await log_change(db, record_type="occurrence", record_id=occ.id, user_id=current_user.id, action="update",
                     changed_fields={"old": old, "new": {"idno": data.idno, "occurrence_type": occurrence_type, "status": data.status}})
    try:
        await search_service.index_record("occurrence", occ, db)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    return occ


@router.post("/{occ_id}/publish")
async def publish_occurrence(
    occ_id: uuid.UUID,
    db: DBDep,
    current_user=require_admin_or_editor(),
) -> dict:
    """Publish an occurrence after validating required fields."""
    ok, errors = await can_publish(db, "occurrence", str(occ_id))
    if not ok:
        raise HTTPException(status_code=422, detail={"errors": errors})
    result = await publish_record(db, "occurrence", str(occ_id), str(current_user.id))
    await db.commit()
    return result


@router.delete("/{occ_id}", status_code=204)
async def delete_occurrence(
    occ_id: uuid.UUID,
    db: DBDep,
    current_user=require_admin_or_editor(),
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

    if related_count > 0:
        await delete_relations(db, "occurrence", occ_id)

    await log_change(db, record_type="occurrence", record_id=occ.id, user_id=current_user.id, action="delete")
    try:
        await search_service.remove_record(occ.id)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    await db.delete(occ)

    from katalon.workers.cleanup_tasks import cleanup_relation_refs
    cleanup_relation_refs.delay("occurrence", str(occ_id))


@router.post("/{occ_id}/snapshots", response_model=SnapshotRead, status_code=201)
async def create_snapshot(
    occ_id: uuid.UUID, data: SnapshotCreate, db: DBDep, current_user=require_admin_or_editor()
) -> RecordSnapshot:
    result = await db.execute(select(Occurrence).where(Occurrence.id == occ_id))
    occ = result.scalar_one_or_none()
    if not occ:
        raise HTTPException(status_code=404, detail="Occurrence nicht gefunden")
    snap = RecordSnapshot(
        record_type="occurrence",
        record_id=occ.id,
        label=data.label,
        snapshot={"occurrence_type": occ.occurrence_type, "status": occ.status, "metadata": occ.metadata_},
        created_by=current_user.id,
    )
    db.add(snap)
    await db.flush()
    return snap


@router.get("/{occ_id}/snapshots", response_model=list[SnapshotRead])
async def list_snapshots(occ_id: uuid.UUID, db: DBDep) -> list[RecordSnapshot]:
    result = await db.execute(
        select(RecordSnapshot)
        .where(RecordSnapshot.record_type == "occurrence", RecordSnapshot.record_id == occ_id)
        .order_by(RecordSnapshot.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/{occ_id}/snapshots/{snapshot_id}/restore", response_model=OccurrenceRead)
async def restore_snapshot(
    occ_id: uuid.UUID, snapshot_id: uuid.UUID, db: DBDep, _=require_admin_or_editor()
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

    data = snap.snapshot
    if "occurrence_type" in data:
        occ.occurrence_type = data["occurrence_type"]
    if "status" in data:
        occ.status = data["status"]
    if "metadata" in data:
        occ.metadata_ = data["metadata"]
    await db.flush()
    return occ


@router.get("/{occ_id}/audit-log", response_model=list[AuditLogRead])
async def list_occurrence_audit_log(occ_id: uuid.UUID, db: DBDep) -> list[AuditLogRead]:
    from katalon.api.v1.audit import list_audit_log
    return await list_audit_log(db, record_type="occurrence", record_id=occ_id, limit=100)
