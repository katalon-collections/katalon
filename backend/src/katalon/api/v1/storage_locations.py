# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import Text, and_, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.concurrency import check_version, flush_record
from katalon.core.dependencies import DBDep, OptionalCurrentUser, require_record_permission
from katalon.core.list_query import SortBy, SortDir, apply_sort
from katalon.core.models import AdminConfig, StorageLocation, User
from katalon.core.schemas import StorageLocationCreate, StorageLocationRead
from katalon.services import search_service
from katalon.services.audit_service import delete_label_fields, diff_fields, log_change
from katalon.services.idno_service import (
    consume_next_idno,
    maybe_advance_counter,
    validate_idno_pattern,
)
from katalon.services.lock_service import enforce_not_locked
from katalon.services.presence_service import enforce_not_blocked
from katalon.services.relation_service import count_relations, sync_schema_relations
from katalon.services.schema_service import prepare_metadata, validate_metadata
from katalon.services.subtype_service import ensure_subtype_exists, normalize_subtype_name

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/storage-locations", tags=["storage-locations"])


async def _validate_parent_id(
    db: AsyncSession,
    storage_location_id: uuid.UUID | None,
    parent_id: uuid.UUID | None,
) -> None:
    if parent_id is None:
        return
    if storage_location_id is not None and parent_id == storage_location_id:
        raise HTTPException(
            status_code=422,
            detail="Ein Lagerort kann nicht sein eigener übergeordneter Lagerort sein.",
        )

    parent = (
        await db.execute(
            select(StorageLocation).where(
                StorageLocation.id == parent_id,
                StorageLocation.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if parent is None:
        raise HTTPException(
            status_code=422,
            detail="Übergeordneter Lagerort existiert nicht.",
        )

    if storage_location_id is not None:
        curr_parent_id: uuid.UUID | None = parent.parent_id
        visited: set[uuid.UUID] = {storage_location_id, parent_id}
        while curr_parent_id is not None:
            if curr_parent_id == storage_location_id:
                raise HTTPException(
                    status_code=422,
                    detail="Zyklische Lagerort-Hierarchie ist nicht erlaubt.",
                )
            if curr_parent_id in visited:
                break
            visited.add(curr_parent_id)
            curr_parent_id = (
                await db.execute(
                    select(StorageLocation.parent_id).where(StorageLocation.id == curr_parent_id)
                )
            ).scalar_one_or_none()


@router.get(
    "",
    response_model=dict[str, Any],
    summary="List storage locations with pagination and filters",
)
async def list_storage_locations(
    db: DBDep,
    current_user: OptionalCurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    storage_location_type: str | None = None,
    parent_id: uuid.UUID | None = None,
    q: str | None = None,
    sort_by: SortBy | None = None,
    sort_dir: SortDir = "desc",
) -> dict[str, Any]:
    query = select(StorageLocation).where(StorageLocation.deleted_at.is_(None))
    if storage_location_type:
        query = query.where(StorageLocation.storage_location_type == storage_location_type)
    if parent_id is not None:
        query = query.where(StorageLocation.parent_id == parent_id)
    if q:
        query = query.where(
            StorageLocation.idno.icontains(q, autoescape=True)
            | cast(StorageLocation.metadata_, Text).icontains(q, autoescape=True)
        )
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    query = apply_sort(
        query.offset((page - 1) * page_size).limit(page_size),
        StorageLocation,
        sort_by,
        sort_dir,
    )
    items = (await db.execute(query)).scalars().all()
    response_items = [StorageLocationRead.model_validate(i) for i in items]
    return {"total": total, "page": page, "page_size": page_size, "items": response_items}


@router.post(
    "",
    response_model=StorageLocationRead,
    status_code=201,
    summary="Create a new storage location record",
    responses={
        403: {"description": "Insufficient permissions"},
        400: {"description": "Idno already taken"},
        422: {"description": "Idno missing/invalid pattern or metadata validation failed"},
    },
)
async def create_storage_location(
    data: StorageLocationCreate,
    db: DBDep,
    current_user: User = require_record_permission("storage_location", "create"),
) -> StorageLocation:
    cfg_result = await db.execute(select(AdminConfig).where(AdminConfig.key == "default"))
    cfg = cfg_result.scalar_one_or_none()
    schema = (cfg.idno_schemas or {}).get("storage_location") if cfg else None
    pattern = (cfg.idno_patterns or {}).get("storage_location") if cfg else None

    if not data.idno or not data.idno.strip():
        if schema:
            idno = await consume_next_idno(db, "storage_location", schema)
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
            await maybe_advance_counter(db, "storage_location", schema, idno)
        existing = await db.execute(select(StorageLocation).where(StorageLocation.idno == idno))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="ID-Nr. bereits vergeben.")

    await _validate_parent_id(db, None, data.parent_id)

    storage_location_type = normalize_subtype_name(
        data.storage_location_type,
        allow_null=True,
    )
    await ensure_subtype_exists(db, "storage_location", storage_location_type)
    metadata = await prepare_metadata(
        db,
        "storage_location",
        data.metadata_,
        storage_location_type,
        existing=None,
        can_edit_locked=current_user.role in {"admin", "superuser"},
    )
    errors = await validate_metadata(db, "storage_location", metadata, storage_location_type)
    if errors:
        raise HTTPException(status_code=422, detail=errors)

    loc = StorageLocation(
        idno=idno,
        storage_location_type=storage_location_type,
        parent_id=data.parent_id,
        metadata_=metadata,
    )
    db.add(loc)
    await flush_record(db, loc)
    await sync_schema_relations(db, "storage_location", loc.id, metadata)
    await log_change(
        db,
        record_type="storage_location",
        record_id=loc.id,
        user_id=current_user.id,
        action="create",
    )
    try:
        await search_service.index_record("storage_location", loc, db)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    return loc


@router.get(
    "/{loc_id}",
    response_model=StorageLocationRead,
    summary="Get a single storage location by ID",
    responses={
        404: {"description": "Storage location not found"},
    },
)
async def get_storage_location(
    loc_id: uuid.UUID,
    db: DBDep,
    current_user: OptionalCurrentUser,
) -> StorageLocation:
    result = await db.execute(
        select(StorageLocation).where(
            StorageLocation.id == loc_id, StorageLocation.deleted_at.is_(None)
        )
    )
    loc = result.scalar_one_or_none()
    if not loc:
        raise HTTPException(status_code=404, detail="Lagerort nicht gefunden")
    return loc


@router.put(
    "/{loc_id}",
    response_model=StorageLocationRead,
    summary="Update a storage location record",
    responses={
        404: {"description": "Storage location not found"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Version conflict (If-Match mismatch)"},
        400: {"description": "Idno already taken"},
        422: {"description": "Idno missing or metadata validation failed"},
    },
)
async def update_storage_location(
    loc_id: uuid.UUID,
    data: StorageLocationCreate,
    db: DBDep,
    current_user: User = require_record_permission("storage_location", "update"),
    if_match: int | None = Header(None, alias="If-Match"),
) -> StorageLocation:
    result = await db.execute(select(StorageLocation).where(StorageLocation.id == loc_id))
    loc = result.scalar_one_or_none()
    if not loc:
        raise HTTPException(status_code=404, detail="Lagerort nicht gefunden")
    check_version(loc.version, if_match)
    await enforce_not_blocked(db, "storage_location", loc.id, current_user)
    await enforce_not_locked(db, "storage_location", loc.id, current_user)

    if not data.idno or not data.idno.strip():
        raise HTTPException(status_code=422, detail="ID-Nr. ist ein Pflichtfeld.")
    else:
        idno = data.idno.strip()
        existing = await db.execute(
            select(StorageLocation).where(
                StorageLocation.idno == idno, StorageLocation.id != loc_id
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="ID-Nr. bereits vergeben.")

    await _validate_parent_id(db, loc_id, data.parent_id)

    storage_location_type = normalize_subtype_name(
        data.storage_location_type,
        allow_null=True,
    )
    await ensure_subtype_exists(db, "storage_location", storage_location_type)
    metadata = await prepare_metadata(
        db,
        "storage_location",
        data.metadata_,
        storage_location_type,
        existing=loc.metadata_,
        can_edit_locked=current_user.role in {"admin", "superuser"},
    )
    errors = await validate_metadata(db, "storage_location", metadata, storage_location_type)
    if errors:
        raise HTTPException(status_code=422, detail=errors)

    old = {
        "idno": loc.idno,
        "storage_location_type": loc.storage_location_type,
        "parent_id": str(loc.parent_id) if loc.parent_id else None,
        "metadata": loc.metadata_,
    }
    loc.idno = idno
    loc.storage_location_type = storage_location_type
    loc.parent_id = data.parent_id
    loc.metadata_ = metadata

    await flush_record(db, loc)
    await sync_schema_relations(db, "storage_location", loc.id, metadata)
    loc_diff = diff_fields(
        old,
        {
            "idno": idno,
            "storage_location_type": storage_location_type,
            "parent_id": str(data.parent_id) if data.parent_id else None,
            "metadata": metadata,
        },
    )
    if loc_diff:
        await log_change(
            db,
            record_type="storage_location",
            record_id=loc.id,
            user_id=current_user.id,
            action="update",
            changed_fields=loc_diff,
        )
    try:
        await search_service.index_record("storage_location", loc, db)
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)
    return loc


@router.delete(
    "/{loc_id}",
    status_code=204,
    summary="Delete a storage location record",
    responses={
        404: {"description": "Storage location not found"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Record has linked relations (pass force=true to delete anyway)"},
    },
)
async def delete_storage_location(
    loc_id: uuid.UUID,
    db: DBDep,
    current_user: User = require_record_permission("storage_location", "delete"),
    force: bool = Query(False),
) -> None:
    result = await db.execute(select(StorageLocation).where(StorageLocation.id == loc_id))
    loc = result.scalar_one_or_none()
    if not loc:
        raise HTTPException(status_code=404, detail="Lagerort nicht gefunden")

    related_count = await count_relations(db, "storage_location", loc_id)
    if related_count > 0 and not force:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": f"Dieser Datensatz ist mit {related_count} anderen Datensätzen verknüpft.",
                "related_count": related_count,
            },
        )

    loc.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    await log_change(
        db,
        record_type="storage_location",
        record_id=loc.id,
        user_id=current_user.id,
        action="delete",
        changed_fields=delete_label_fields(loc.idno, loc.metadata_),
    )
    await flush_record(db, loc)
    try:
        await search_service.remove_record(loc.id, record_type="storage_location")
    except Exception:
        logger.warning("ES index/remove failed", exc_info=True)

    from katalon.workers.cleanup_tasks import cleanup_relation_refs
    from katalon.workers.enqueue import enqueue

    enqueue(cleanup_relation_refs, "storage_location", str(loc_id))


class StorageLocationObjectRead(BaseModel):
    id: uuid.UUID
    idno: str | None = None
    title: str = ""
    object_type: str | None = None
    status: str = "draft"
    relation_type: str | None = None
    storage_location_id: uuid.UUID
    storage_location_idno: str | None = None


class StorageLocationObjectsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[StorageLocationObjectRead]


@router.get(
    "/{loc_id}/objects",
    response_model=StorageLocationObjectsResponse,
    summary="List objects stored at this location (optionally including sublocations)",
)
async def list_storage_location_objects(
    loc_id: uuid.UUID,
    db: DBDep,
    current_user: OptionalCurrentUser,
    include_sublocations: bool = True,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> StorageLocationObjectsResponse:
    from katalon.core.models import Object, Relation
    from katalon.services.search_service import _extract_title
    from katalon.services.storage_location_service import get_storage_location_subtree_ids

    loc = await db.get(StorageLocation, loc_id)
    if not loc or loc.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Lagerort nicht gefunden")

    loc_ids = (
        await get_storage_location_subtree_ids(db, loc_id) if include_sublocations else [loc_id]
    )

    locs_res = await db.execute(
        select(StorageLocation.id, StorageLocation.idno).where(
            StorageLocation.id.in_(loc_ids), StorageLocation.deleted_at.is_(None)
        )
    )
    loc_idno_map = {row.id: row.idno for row in locs_res.all()}

    rel_stmt = select(Relation).where(
        or_(
            and_(
                Relation.from_type == "object",
                Relation.to_type == "storage_location",
                Relation.to_id.in_(loc_ids),
            ),
            and_(
                Relation.from_type == "storage_location",
                Relation.to_type == "object",
                Relation.from_id.in_(loc_ids),
            ),
        )
    )
    relations = list((await db.execute(rel_stmt)).scalars().all())

    obj_rel_map: dict[uuid.UUID, tuple[uuid.UUID, str | None]] = {}
    for rel in relations:
        if rel.from_type == "object":
            obj_id = rel.from_id
            l_id = rel.to_id
        else:
            obj_id = rel.to_id
            l_id = rel.from_id
        if obj_id not in obj_rel_map:
            obj_rel_map[obj_id] = (l_id, rel.relation_type)

    if not obj_rel_map:
        return StorageLocationObjectsResponse(total=0, page=page, page_size=page_size, items=[])

    obj_ids = list(obj_rel_map.keys())
    count_stmt = select(func.count()).select_from(
        select(Object.id)
        .where(
            Object.id.in_(obj_ids),
            Object.deleted_at.is_(None),
        )
        .subquery()
    )
    total = (await db.execute(count_stmt)).scalar_one()

    query = (
        select(Object)
        .where(
            Object.id.in_(obj_ids),
            Object.deleted_at.is_(None),
        )
        .order_by(Object.idno.asc().nulls_last(), Object.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    objects = list((await db.execute(query)).scalars().all())

    items: list[StorageLocationObjectRead] = []
    for obj in objects:
        l_id, rel_type = obj_rel_map.get(obj.id, (loc_id, None))
        title = _extract_title(obj.metadata_ or {})
        items.append(
            StorageLocationObjectRead(
                id=obj.id,
                idno=obj.idno,
                title=title,
                object_type=obj.object_type,
                status=obj.status,
                relation_type=rel_type,
                storage_location_id=l_id,
                storage_location_idno=loc_idno_map.get(l_id),
            )
        )

    return StorageLocationObjectsResponse(total=total, page=page, page_size=page_size, items=items)
