import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.dependencies import CurrentUser, DBDep
from katalon.core.models import Object, RecordSnapshot
from katalon.core.schemas import ObjectCreate, ObjectRead, SnapshotCreate, SnapshotRead
from katalon.services.audit_service import log_change
from katalon.services.schema_service import validate_metadata
from katalon.services import search_service

router = APIRouter(prefix="/objects", tags=["objects"])


@router.get("", response_model=dict)
async def list_objects(
    db: DBDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: str | None = None,
    q: str | None = None,
) -> dict:
    query = select(Object)
    if status:
        query = query.where(Object.status == status)
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
    errors = await validate_metadata(db, "object", data.metadata_)
    if errors:
        raise HTTPException(status_code=422, detail=errors)

    obj = Object(idno=data.idno, status=data.status, metadata_=data.metadata_)
    db.add(obj)
    await db.flush()
    await log_change(db, record_type="object", record_id=obj.id, user_id=current_user.id, action="create")
    try:
        await search_service.index_record("object", obj)
    except Exception:
        pass
    return obj


@router.get("/{object_id}", response_model=ObjectRead)
async def get_object(object_id: uuid.UUID, db: DBDep) -> Object:
    result = await db.execute(select(Object).where(Object.id == object_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden")
    return obj


@router.put("/{object_id}", response_model=ObjectRead)
async def update_object(
    object_id: uuid.UUID, data: ObjectCreate, db: DBDep, current_user: CurrentUser
) -> Object:
    result = await db.execute(select(Object).where(Object.id == object_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden")

    errors = await validate_metadata(db, "object", data.metadata_)
    if errors:
        raise HTTPException(status_code=422, detail=errors)

    old_fields = {"status": obj.status, "metadata": obj.metadata_}
    obj.idno = data.idno
    obj.status = data.status
    obj.metadata_ = data.metadata_

    await log_change(
        db,
        record_type="object",
        record_id=obj.id,
        user_id=current_user.id,
        action="update",
        changed_fields={"old": old_fields, "new": {"status": data.status, "metadata": data.metadata_}},
    )
    try:
        await search_service.index_record("object", obj)
    except Exception:
        pass
    return obj


@router.delete("/{object_id}", status_code=204)
async def delete_object(object_id: uuid.UUID, db: DBDep, current_user: CurrentUser) -> None:
    result = await db.execute(select(Object).where(Object.id == object_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden")
    await log_change(db, record_type="object", record_id=obj.id, user_id=current_user.id, action="delete")
    try:
        await search_service.remove_record(obj.id)
    except Exception:
        pass
    await db.delete(obj)


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
        snapshot={"idno": obj.idno, "status": obj.status, "metadata": obj.metadata_},
        created_by=current_user.id,
    )
    db.add(snap)
    await db.flush()
    return snap


@router.get("/{object_id}/snapshots", response_model=list[SnapshotRead])
async def list_snapshots(object_id: uuid.UUID, db: DBDep) -> list[RecordSnapshot]:
    result = await db.execute(
        select(RecordSnapshot)
        .where(RecordSnapshot.record_type == "object", RecordSnapshot.record_id == object_id)
        .order_by(RecordSnapshot.created_at.desc())
    )
    return list(result.scalars().all())
