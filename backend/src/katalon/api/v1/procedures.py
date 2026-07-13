import logging
import uuid
from datetime import date

from fastapi import APIRouter, Header, HTTPException, Query
from sqlalchemy import func, select

from katalon.core.concurrency import check_version
from katalon.core.dependencies import DBDep, require_admin_or_editor
from katalon.core.models import AdminConfig, Object, Procedure, RecordSnapshot
from katalon.core.schemas import (
    AuditLogRead,
    ProcedureComplete,
    ProcedureCreate,
    ProcedureRead,
    SnapshotCreate,
    SnapshotRead,
)
from katalon.services import search_service
from katalon.services.audit_service import log_change
from katalon.services.idno_service import (
    consume_next_idno,
    maybe_advance_counter,
    validate_idno_pattern,
)
from katalon.services.relation_service import (
    count_relations,
    delete_relations,
    get_active_loan_out_for_object,
    procedure_object_ids,
    sync_schema_relations,
)
from katalon.services.schema_service import prepare_metadata, validate_metadata

router = APIRouter(prefix="/procedures", tags=["procedures"])
logger = logging.getLogger(__name__)

PROCEDURE_TYPES = {
    "loan_out",
    "loan_in",
    "acquisition",
    "conservation",
    "object_entry",
    "deaccession",
}
PROCEDURE_STATUSES = {"draft", "active", "completed", "cancelled"}
COLLECTION_STATUSES = {"active", "pending", "on_loan_in", "on_loan_out", "deaccessioned", "returned"}


async def _validate_procedure(
    data: ProcedureCreate,
    db: DBDep,
    procedure_id: uuid.UUID | None = None,
) -> None:
    procedure_type = data.procedure_type.strip()
    if not procedure_type:
        if data.status == "draft":
            return
        raise HTTPException(status_code=422, detail="Vorgangstyp ist erforderlich.")
    if procedure_type not in PROCEDURE_TYPES:
        raise HTTPException(status_code=422, detail="Ungültiger Vorgangstyp.")
    if data.status not in PROCEDURE_STATUSES:
        raise HTTPException(status_code=422, detail="Ungültiger Vorgangsstatus.")
    errors = await validate_metadata(
        db,
        "procedure",
        data.metadata_,
        procedure_type,
        skip_required=data.status == "draft",
    )
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    if procedure_type == "loan_out" and data.status == "active" and procedure_id:
        for object_id in await procedure_object_ids(db, procedure_id):
            existing = await get_active_loan_out_for_object(
                db,
                object_id,
                exclude_procedure_id=procedure_id,
            )
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail="Objekt ist bereits in einem aktiven Ausleihvorgang.",
                )


async def _idno(data: ProcedureCreate, db: DBDep) -> str | None:
    cfg = (
        await db.execute(select(AdminConfig).where(AdminConfig.key == "default"))
    ).scalar_one_or_none()
    schema = (cfg.idno_schemas or {}).get("procedure") if cfg else None
    pattern = (cfg.idno_patterns or {}).get("procedure") if cfg else None
    if not data.idno or not data.idno.strip():
        if schema:
            return await consume_next_idno(db, "procedure", schema)
        if data.status == "draft":
            return None
        raise HTTPException(status_code=422, detail="ID-Nr. ist ein Pflichtfeld.")
    idno = data.idno.strip()
    if pattern and not validate_idno_pattern(pattern, idno):
        raise HTTPException(
            status_code=422,
            detail=f"ID-Nr. entspricht nicht dem Muster: {pattern}",
        )
    if schema:
        await maybe_advance_counter(db, "procedure", schema, idno)
    return idno


@router.get("", response_model=dict)
async def list_procedures(
    db: DBDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    procedure_type: str | None = None,
    status: str | None = None,
    due_before: date | None = None,
    reference_number: str | None = None,
    q: str | None = None,
) -> dict:
    query = select(Procedure)
    if procedure_type:
        query = query.where(Procedure.procedure_type == procedure_type)
    if status:
        query = query.where(Procedure.status == status)
    if due_before:
        query = query.where(Procedure.due_date <= due_before)
    if reference_number:
        query = query.where(Procedure.reference_number.ilike(f"%{reference_number}%"))
    if q:
        query = query.where(Procedure.search_vector.match(q))
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    query = (
        query.offset((page - 1) * page_size)
        .limit(page_size)
        .order_by(Procedure.updated_at.desc())
    )
    items = (await db.execute(query)).scalars().all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [ProcedureRead.model_validate(i) for i in items],
    }


@router.post("", response_model=ProcedureRead, status_code=201)
async def create_procedure(
    data: ProcedureCreate,
    db: DBDep,
    current_user=require_admin_or_editor(),
) -> Procedure:
    procedure_type = data.procedure_type.strip()
    metadata = await prepare_metadata(
        db, "procedure", data.metadata_, procedure_type or None,
        can_edit_locked=current_user.role in {"admin", "superuser"},
    )
    data = data.model_copy(update={"metadata_": metadata, "procedure_type": procedure_type})
    await _validate_procedure(data, db)
    idno = await _idno(data, db)
    if idno is not None:
        existing = await db.execute(select(Procedure).where(Procedure.idno == idno))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="ID-Nr. bereits vergeben.")
    proc = Procedure(
        idno=idno,
        procedure_type=data.procedure_type,
        status=data.status,
        start_date=data.start_date,
        end_date=data.end_date,
        due_date=data.due_date,
        reference_number=data.reference_number,
        metadata_=data.metadata_,
    )
    db.add(proc)
    await db.flush()
    await sync_schema_relations(db, "procedure", proc.id, data.metadata_)
    await db.flush()
    await log_change(
        db,
        record_type="procedure",
        record_id=proc.id,
        user_id=current_user.id,
        action="create",
    )
    try:
        await search_service.index_record("procedure", proc, db)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    return proc


@router.post("/{procedure_id}/complete", response_model=ProcedureRead)
async def complete_procedure(
    procedure_id: uuid.UUID,
    data: ProcedureComplete,
    db: DBDep,
    current_user=require_admin_or_editor(),
) -> Procedure:
    proc = (
        await db.execute(select(Procedure).where(Procedure.id == procedure_id))
    ).scalar_one_or_none()
    if not proc:
        raise HTTPException(status_code=404, detail="Vorgang nicht gefunden")
    if data.collection_status and data.collection_status not in COLLECTION_STATUSES:
        raise HTTPException(status_code=422, detail="Ungültiger Sammlungsstatus.")

    old_status = proc.status
    proc.status = "completed"

    changed_objects: list[str] = []
    if data.collection_status:
        object_ids = await procedure_object_ids(db, procedure_id)
        if object_ids:
            result = await db.execute(select(Object).where(Object.id.in_(object_ids)))
            for obj in result.scalars().all():
                old_collection_status = obj.collection_status
                obj.collection_status = data.collection_status
                changed_objects.append(str(obj.id))
                await log_change(
                    db,
                    record_type="object",
                    record_id=obj.id,
                    user_id=current_user.id,
                    action="update",
                    changed_fields={
                        "old": {"collection_status": old_collection_status},
                        "new": {"collection_status": data.collection_status},
                    },
                )
                try:
                    await search_service.index_record("object", obj, db)
                except Exception:
                    logger.warning("ES index/remove failed", exc_info=True)

    await log_change(
        db,
        record_type="procedure",
        record_id=proc.id,
        user_id=current_user.id,
        action="update",
        changed_fields={
            "old": {"status": old_status},
            "new": {
                "status": "completed",
                "collection_status": data.collection_status,
                "object_ids": changed_objects,
            },
        },
    )
    await db.flush()
    try:
        await search_service.index_record("procedure", proc, db)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    return proc


@router.get("/{procedure_id}", response_model=ProcedureRead)
async def get_procedure(procedure_id: uuid.UUID, db: DBDep) -> Procedure:
    proc = (
        await db.execute(select(Procedure).where(Procedure.id == procedure_id))
    ).scalar_one_or_none()
    if not proc:
        raise HTTPException(status_code=404, detail="Vorgang nicht gefunden")
    return proc


@router.put("/{procedure_id}", response_model=ProcedureRead)
async def update_procedure(
    procedure_id: uuid.UUID,
    data: ProcedureCreate,
    db: DBDep,
    current_user=require_admin_or_editor(),
    if_match: int | None = Header(None, alias="If-Match"),
) -> Procedure:
    proc = (
        await db.execute(select(Procedure).where(Procedure.id == procedure_id))
    ).scalar_one_or_none()
    if not proc:
        raise HTTPException(status_code=404, detail="Vorgang nicht gefunden")
    check_version(proc.version, if_match)
    procedure_type = data.procedure_type.strip()
    metadata = await prepare_metadata(
        db, "procedure", data.metadata_, procedure_type or None, existing=proc.metadata_,
        can_edit_locked=current_user.role in {"admin", "superuser"},
    )
    data = data.model_copy(update={"metadata_": metadata, "procedure_type": procedure_type})
    if not data.idno or not data.idno.strip():
        if data.status == "draft":
            idno = None
        else:
            raise HTTPException(status_code=422, detail="ID-Nr. ist ein Pflichtfeld.")
    else:
        idno = data.idno.strip()
        existing = await db.execute(
            select(Procedure).where(
                Procedure.idno == idno,
                Procedure.id != procedure_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="ID-Nr. bereits vergeben.")
    await _validate_procedure(data, db, procedure_id)
    old = {
        "idno": proc.idno,
        "procedure_type": proc.procedure_type,
        "status": proc.status,
        "start_date": proc.start_date.isoformat() if proc.start_date else None,
        "end_date": proc.end_date.isoformat() if proc.end_date else None,
        "due_date": proc.due_date.isoformat() if proc.due_date else None,
        "reference_number": proc.reference_number,
        "metadata": proc.metadata_,
    }
    proc.idno = idno
    proc.procedure_type = data.procedure_type
    proc.status = data.status
    proc.start_date = data.start_date
    proc.end_date = data.end_date
    proc.due_date = data.due_date
    proc.reference_number = data.reference_number
    proc.metadata_ = data.metadata_
    proc.version += 1
    await sync_schema_relations(db, "procedure", proc.id, data.metadata_)
    await log_change(
        db,
        record_type="procedure",
        record_id=proc.id,
        user_id=current_user.id,
        action="update",
        changed_fields={
            "old": old,
            "new": ProcedureRead.model_validate(proc).model_dump(mode="json"),
        },
    )
    try:
        await search_service.index_record("procedure", proc, db)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    return proc


@router.delete("/{procedure_id}", status_code=204)
async def delete_procedure(
    procedure_id: uuid.UUID,
    db: DBDep,
    current_user=require_admin_or_editor(),
    force: bool = Query(False),
) -> None:
    proc = (
        await db.execute(select(Procedure).where(Procedure.id == procedure_id))
    ).scalar_one_or_none()
    if not proc:
        raise HTTPException(status_code=404, detail="Vorgang nicht gefunden")
    related_count = await count_relations(db, "procedure", procedure_id)
    if related_count > 0 and not force:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": (
                    f"Dieser Datensatz ist mit {related_count} anderen Datensätzen "
                    "verknüpft."
                ),
                "related_count": related_count,
            },
        )
    if related_count > 0:
        await delete_relations(db, "procedure", procedure_id)
    await log_change(
        db,
        record_type="procedure",
        record_id=proc.id,
        user_id=current_user.id,
        action="delete",
    )
    await db.delete(proc)
    try:
        await search_service.remove_record(procedure_id)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)

    from katalon.workers.cleanup_tasks import cleanup_relation_refs
    cleanup_relation_refs.delay("procedure", str(procedure_id))


@router.post("/{procedure_id}/snapshots", response_model=SnapshotRead, status_code=201)
async def create_snapshot(
    procedure_id: uuid.UUID,
    data: SnapshotCreate,
    db: DBDep,
    current_user=require_admin_or_editor(),
) -> RecordSnapshot:
    proc = (
        await db.execute(select(Procedure).where(Procedure.id == procedure_id))
    ).scalar_one_or_none()
    if not proc:
        raise HTTPException(status_code=404, detail="Vorgang nicht gefunden")
    snap = RecordSnapshot(
        record_type="procedure",
        record_id=proc.id,
        label=data.label,
        snapshot=ProcedureRead.model_validate(proc).model_dump(mode="json"),
        created_by=current_user.id,
    )
    db.add(snap)
    await db.flush()
    return snap


@router.get("/{procedure_id}/snapshots", response_model=list[SnapshotRead])
async def list_snapshots(procedure_id: uuid.UUID, db: DBDep) -> list[RecordSnapshot]:
    result = await db.execute(
        select(RecordSnapshot)
        .where(RecordSnapshot.record_type == "procedure", RecordSnapshot.record_id == procedure_id)
        .order_by(RecordSnapshot.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/{procedure_id}/snapshots/{snapshot_id}/restore", response_model=ProcedureRead)
async def restore_snapshot(
    procedure_id: uuid.UUID, snapshot_id: uuid.UUID, db: DBDep, _=require_admin_or_editor()
) -> Procedure:
    snap = (
        await db.execute(
            select(RecordSnapshot).where(
                RecordSnapshot.id == snapshot_id,
                RecordSnapshot.record_type == "procedure",
                RecordSnapshot.record_id == procedure_id,
            )
        )
    ).scalar_one_or_none()
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot nicht gefunden")
    proc = (
        await db.execute(select(Procedure).where(Procedure.id == procedure_id))
    ).scalar_one_or_none()
    if not proc:
        raise HTTPException(status_code=404, detail="Vorgang nicht gefunden")
    for key in ("procedure_type", "status", "reference_number", "metadata_"):
        if key in snap.snapshot:
            setattr(proc, key, snap.snapshot[key])
    for key in ("start_date", "end_date", "due_date"):
        if key in snap.snapshot:
            value = snap.snapshot[key]
            setattr(proc, key, date.fromisoformat(value) if value else None)
    await db.flush()
    return proc


@router.get("/{procedure_id}/audit-log", response_model=list[AuditLogRead])
async def list_procedure_audit_log(procedure_id: uuid.UUID, db: DBDep) -> list[AuditLogRead]:
    from katalon.api.v1.audit import list_audit_log
    return await list_audit_log(db, record_type="procedure", record_id=procedure_id, limit=100)
