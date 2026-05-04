import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from katalon.core.dependencies import CurrentUser, DBDep
from katalon.core.models import Place, RecordSnapshot
from katalon.core.schemas import AuditLogRead, PlaceCreate, PlaceRead, SnapshotCreate, SnapshotRead
from katalon.services.audit_service import log_change
from katalon.services.schema_service import validate_metadata
from katalon.services import search_service

router = APIRouter(prefix="/places", tags=["places"])


@router.get("", response_model=dict)
async def list_places(
    db: DBDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: str | None = None,
    q: str | None = None,
) -> dict:
    query = select(Place)
    if status:
        query = query.where(Place.status == status)
    if q:
        query = query.where(Place.search_vector.match(q))
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    query = query.offset((page - 1) * page_size).limit(page_size).order_by(Place.updated_at.desc())
    items = (await db.execute(query)).scalars().all()
    return {"total": total, "page": page, "page_size": page_size, "items": [PlaceRead.model_validate(i) for i in items]}


@router.post("", response_model=PlaceRead, status_code=201)
async def create_place(data: PlaceCreate, db: DBDep, current_user: CurrentUser) -> Place:
    errors = await validate_metadata(db, "place", data.metadata_)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    place = Place(status=data.status, metadata_=data.metadata_)
    if data.lat is not None and data.lon is not None:
        from geoalchemy2.elements import WKTElement
        place.geom = WKTElement(f"POINT({data.lon} {data.lat})", srid=4326)
    db.add(place)
    await db.flush()
    await log_change(db, record_type="place", record_id=place.id, user_id=current_user.id, action="create")
    try:
        await search_service.index_record("place", place)
    except Exception:
        pass
    return place


@router.get("/{place_id}", response_model=PlaceRead)
async def get_place(place_id: uuid.UUID, db: DBDep) -> Place:
    result = await db.execute(select(Place).where(Place.id == place_id))
    place = result.scalar_one_or_none()
    if not place:
        raise HTTPException(status_code=404, detail="Ort nicht gefunden")
    return place


@router.put("/{place_id}", response_model=PlaceRead)
async def update_place(place_id: uuid.UUID, data: PlaceCreate, db: DBDep, current_user: CurrentUser) -> Place:
    result = await db.execute(select(Place).where(Place.id == place_id))
    place = result.scalar_one_or_none()
    if not place:
        raise HTTPException(status_code=404, detail="Ort nicht gefunden")
    errors = await validate_metadata(db, "place", data.metadata_)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
    old = {"status": place.status, "metadata": place.metadata_}
    place.status = data.status
    place.metadata_ = data.metadata_
    if data.lat is not None and data.lon is not None:
        from geoalchemy2.elements import WKTElement
        place.geom = WKTElement(f"POINT({data.lon} {data.lat})", srid=4326)
    await log_change(db, record_type="place", record_id=place.id, user_id=current_user.id, action="update",
                     changed_fields={"old": old, "new": {"status": data.status}})
    try:
        await search_service.index_record("place", place)
    except Exception:
        pass
    return place


@router.delete("/{place_id}", status_code=204)
async def delete_place(place_id: uuid.UUID, db: DBDep, current_user: CurrentUser) -> None:
    result = await db.execute(select(Place).where(Place.id == place_id))
    place = result.scalar_one_or_none()
    if not place:
        raise HTTPException(status_code=404, detail="Ort nicht gefunden")
    await log_change(db, record_type="place", record_id=place.id, user_id=current_user.id, action="delete")
    try:
        await search_service.remove_record(place.id)
    except Exception:
        pass
    await db.delete(place)


@router.get("/{place_id}/audit-log", response_model=list[AuditLogRead])
async def list_place_audit_log(place_id: uuid.UUID, db: DBDep) -> list[AuditLogRead]:
    from katalon.api.v1.audit import list_audit_log
    return await list_audit_log(db, record_type="place", record_id=place_id, limit=100)
