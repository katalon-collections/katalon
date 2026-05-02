import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from katalon.core.dependencies import CurrentUser, DBDep
from katalon.core.models import Occurrence, RecordSnapshot
from katalon.core.schemas import OccurrenceCreate, OccurrenceRead, SnapshotCreate, SnapshotRead
from katalon.services.audit_service import log_change
from katalon.services.schema_service import validate_metadata
from katalon.services import search_service

router = APIRouter(prefix="/occurrences", tags=["occurrences"])


@router.get("", response_model=dict)
async def list_occurrences(
    db: DBDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    occurrence_type: str | None = None,
    status: str | None = None,
) -> dict:
    query = select(Occurrence)
    if occurrence_type:
        query = query.where(Occurrence.occurrence_type == occurrence_type)
    if status:
        query = query.where(Occurrence.status == status)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    query = query.offset((page - 1) * page_size).limit(page_size).order_by(Occurrence.updated_at.desc())
    items = (await db.execute(query)).scalars().all()
    return {"total": total, "page": page, "page_size": page_size,
            "items": [OccurrenceRead.model_validate(i) for i in items]}


@router.post("", response_model=OccurrenceRead, status_code=201)
async def create_occurrence(data: OccurrenceCreate, db: DBDep, current_user: CurrentUser) -> Occurrence:
    errors = await validate_metadata(db, "occurrence", data.metadata_)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    occ = Occurrence(occurrence_type=data.occurrence_type, status=data.status, metadata_=data.metadata_)
    db.add(occ)
    await db.flush()
    await log_change(db, record_type="occurrence", record_id=occ.id, user_id=current_user.id, action="create")
    try:
        await search_service.index_record("occurrence", occ)
    except Exception:
        pass
    return occ


@router.get("/{occ_id}", response_model=OccurrenceRead)
async def get_occurrence(occ_id: uuid.UUID, db: DBDep) -> Occurrence:
    result = await db.execute(select(Occurrence).where(Occurrence.id == occ_id))
    occ = result.scalar_one_or_none()
    if not occ:
        raise HTTPException(status_code=404, detail="Occurrence nicht gefunden")
    return occ


@router.put("/{occ_id}", response_model=OccurrenceRead)
async def update_occurrence(occ_id: uuid.UUID, data: OccurrenceCreate, db: DBDep, current_user: CurrentUser) -> Occurrence:
    result = await db.execute(select(Occurrence).where(Occurrence.id == occ_id))
    occ = result.scalar_one_or_none()
    if not occ:
        raise HTTPException(status_code=404, detail="Occurrence nicht gefunden")
    errors = await validate_metadata(db, "occurrence", data.metadata_)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    old = {"status": occ.status, "metadata": occ.metadata_}
    occ.occurrence_type = data.occurrence_type
    occ.status = data.status
    occ.metadata_ = data.metadata_
    await log_change(db, record_type="occurrence", record_id=occ.id, user_id=current_user.id, action="update",
                     changed_fields={"old": old, "new": {"status": data.status}})
    try:
        await search_service.index_record("occurrence", occ)
    except Exception:
        pass
    return occ


@router.delete("/{occ_id}", status_code=204)
async def delete_occurrence(occ_id: uuid.UUID, db: DBDep, current_user: CurrentUser) -> None:
    result = await db.execute(select(Occurrence).where(Occurrence.id == occ_id))
    occ = result.scalar_one_or_none()
    if not occ:
        raise HTTPException(status_code=404, detail="Occurrence nicht gefunden")
    await log_change(db, record_type="occurrence", record_id=occ.id, user_id=current_user.id, action="delete")
    try:
        await search_service.remove_record(occ.id)
    except Exception:
        pass
    await db.delete(occ)
