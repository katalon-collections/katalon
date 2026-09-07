# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import (
    MediaFile,
    User,
    WorkingSet,
    WorkingSetItem,
)
from katalon.core.schemas import (
    WorkingSetAddItemsRequest,
    WorkingSetCreate,
    WorkingSetDetailRead,
    WorkingSetItemCreate,
    WorkingSetItemRead,
    WorkingSetItemUpdate,
    WorkingSetRead,
    WorkingSetUpdate,
)
from katalon.services.relation_service import _RECORD_MODELS
from katalon.services.search_service import _extract_title

VALID_RECORD_TYPES = set(_RECORD_MODELS.keys())


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _check_set_access(working_set: WorkingSet, user: User, *, require_owner: bool = False) -> None:
    is_owner = working_set.user_id == user.id
    is_admin = user.role in ("admin", "superuser")

    if require_owner:
        if not (is_owner or is_admin):
            raise HTTPException(
                status_code=403,
                detail="Nur der Besitzer oder Administratoren können diese Arbeitsliste bearbeiten.",
            )
    else:
        if not (is_owner or is_admin or working_set.is_shared):
            raise HTTPException(
                status_code=403,
                detail="Keine Berechtigung für diese Arbeitsliste.",
            )


async def list_working_sets(
    db: AsyncSession,
    user: User,
    *,
    record_type: str | None = None,
    record_id: uuid.UUID | None = None,
) -> list[WorkingSetRead]:
    # Item counts subquery
    counts_subq = (
        select(WorkingSetItem.set_id, func.count(WorkingSetItem.id).label("item_count"))
        .group_by(WorkingSetItem.set_id)
        .subquery()
    )

    query = (
        select(WorkingSet, User.email, func.coalesce(counts_subq.c.item_count, 0).label("cnt"))
        .join(User, WorkingSet.user_id == User.id)
        .outerjoin(counts_subq, WorkingSet.id == counts_subq.c.set_id)
    )

    is_admin = user.role in ("admin", "superuser")
    if not is_admin:
        query = query.where(or_(WorkingSet.user_id == user.id, WorkingSet.is_shared.is_(True)))

    if record_type:
        query = query.where(WorkingSet.record_type == record_type)
    if record_id:
        query = query.where(
            WorkingSet.id.in_(
                select(WorkingSetItem.set_id).where(WorkingSetItem.record_id == record_id)
            )
        )


    query = query.order_by(WorkingSet.updated_at.desc())

    result = await db.execute(query)
    rows = result.all()

    items: list[WorkingSetRead] = []
    for ws, user_email, count in rows:
        items.append(
            WorkingSetRead(
                id=ws.id,
                name=ws.name,
                description=ws.description,
                record_type=ws.record_type,
                user_id=ws.user_id,
                user_name=user_email,
                is_shared=ws.is_shared,
                item_count=count,
                created_at=ws.created_at,
                updated_at=ws.updated_at,
            )
        )
    return items


async def create_working_set(
    db: AsyncSession,
    data: WorkingSetCreate,
    user: User,
) -> WorkingSetRead:
    if data.record_type not in VALID_RECORD_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Ungültiger Datensatztyp: '{data.record_type}'. Gültig sind: {', '.join(sorted(VALID_RECORD_TYPES))}",
        )

    now = _now()
    working_set = WorkingSet(
        name=data.name,
        description=data.description,
        record_type=data.record_type,
        user_id=user.id,
        is_shared=data.is_shared,
        created_at=now,
        updated_at=now,
    )
    db.add(working_set)
    await db.commit()
    await db.refresh(working_set)

    return WorkingSetRead(
        id=working_set.id,
        name=working_set.name,
        description=working_set.description,
        record_type=working_set.record_type,
        user_id=working_set.user_id,
        user_name=user.email,
        is_shared=working_set.is_shared,
        item_count=0,
        created_at=working_set.created_at,
        updated_at=working_set.updated_at,
    )


async def get_working_set_detail(
    db: AsyncSession,
    set_id: uuid.UUID,
    user: User,
) -> WorkingSetDetailRead:
    # Load set with owner
    query = (
        select(WorkingSet, User.email)
        .join(User, WorkingSet.user_id == User.id)
        .where(WorkingSet.id == set_id)
    )
    res = (await db.execute(query)).first()
    if not res:
        raise HTTPException(status_code=404, detail="Arbeitsliste nicht gefunden.")

    ws, user_email = res
    _check_set_access(ws, user)

    # Load items
    items_stmt = (
        select(WorkingSetItem)
        .where(WorkingSetItem.set_id == set_id)
        .order_by(WorkingSetItem.sort_order.asc(), WorkingSetItem.created_at.asc())
    )
    raw_items = list((await db.execute(items_stmt)).scalars().all())

    # Resolve labels, idno, status, and thumbnails
    enriched_items: list[WorkingSetItemRead] = []
    if raw_items:
        record_ids = [item.record_id for item in raw_items]
        model = _RECORD_MODELS.get(ws.record_type)

        records_map: dict[uuid.UUID, Any] = {}
        if model:
            rec_stmt = select(model).where(model.id.in_(record_ids))
            if hasattr(model, "deleted_at"):
                rec_stmt = rec_stmt.where(model.deleted_at.is_(None))
            recs = (await db.execute(rec_stmt)).scalars().all()
            records_map = {r.id: r for r in recs}

        # If record_type == "object", fetch primary media thumbnails
        primary_media_map: dict[uuid.UUID, uuid.UUID] = {}
        if ws.record_type == "object":
            media_stmt = select(MediaFile.object_id, MediaFile.id).where(
                MediaFile.object_id.in_(record_ids),
                MediaFile.is_primary.is_(True),
            )
            for obj_id, m_id in (await db.execute(media_stmt)).all():
                primary_media_map[obj_id] = m_id

        for it in raw_items:
            rec = records_map.get(it.record_id)
            if rec:
                md = getattr(rec, "metadata_", None) or {}
                title = _extract_title(md) or getattr(rec, "idno", None) or str(rec.id)
                idno = getattr(rec, "idno", None)
                status = getattr(rec, "status", None)
                thumb = None
                if it.record_id in primary_media_map:
                    thumb = f"/v1/objects/{it.record_id}/media/{primary_media_map[it.record_id]}/thumbnail"
            else:
                title = "[Gelöscht]"
                idno = None
                status = "deleted"
                thumb = None

            enriched_items.append(
                WorkingSetItemRead(
                    id=it.id,
                    set_id=it.set_id,
                    record_id=it.record_id,
                    sort_order=it.sort_order,
                    note=it.note,
                    created_at=it.created_at,
                    label=title,
                    idno=idno,
                    status=status,
                    thumbnail_url=thumb,
                )
            )

    return WorkingSetDetailRead(
        id=ws.id,
        name=ws.name,
        description=ws.description,
        record_type=ws.record_type,
        user_id=ws.user_id,
        user_name=user_email,
        is_shared=ws.is_shared,
        item_count=len(enriched_items),
        created_at=ws.created_at,
        updated_at=ws.updated_at,
        items=enriched_items,
    )


async def update_working_set(
    db: AsyncSession,
    set_id: uuid.UUID,
    data: WorkingSetUpdate,
    user: User,
) -> WorkingSetRead:
    ws = await db.get(WorkingSet, set_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Arbeitsliste nicht gefunden.")

    _check_set_access(ws, user, require_owner=True)

    if data.name is not None:
        ws.name = data.name
    if data.description is not None:
        ws.description = data.description
    if data.is_shared is not None:
        ws.is_shared = data.is_shared

    ws.updated_at = _now()
    await db.commit()
    await db.refresh(ws)

    # count items
    count_stmt = select(func.count(WorkingSetItem.id)).where(WorkingSetItem.set_id == set_id)
    count = (await db.execute(count_stmt)).scalar_one()

    owner = await db.get(User, ws.user_id)

    return WorkingSetRead(
        id=ws.id,
        name=ws.name,
        description=ws.description,
        record_type=ws.record_type,
        user_id=ws.user_id,
        user_name=owner.email if owner else None,
        is_shared=ws.is_shared,
        item_count=count,
        created_at=ws.created_at,
        updated_at=ws.updated_at,
    )


async def delete_working_set(
    db: AsyncSession,
    set_id: uuid.UUID,
    user: User,
) -> None:
    ws = await db.get(WorkingSet, set_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Arbeitsliste nicht gefunden.")

    _check_set_access(ws, user, require_owner=True)

    await db.delete(ws)
    await db.commit()


async def add_items_to_working_set(
    db: AsyncSession,
    set_id: uuid.UUID,
    data: WorkingSetAddItemsRequest,
    user: User,
) -> list[WorkingSetItemRead]:
    ws = await db.get(WorkingSet, set_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Arbeitsliste nicht gefunden.")

    _check_set_access(ws, user)
    items: list[WorkingSetItemCreate] = list(data.items or [])
    if data.record_ids:
        items.extend(WorkingSetItemCreate(record_id=rid) for rid in data.record_ids)


    # Check which items already exist in this set
    existing_stmt = select(WorkingSetItem.record_id).where(WorkingSetItem.set_id == set_id)
    existing_ids = set((await db.execute(existing_stmt)).scalars().all())

    # Get max sort_order
    max_order_stmt = select(func.coalesce(func.max(WorkingSetItem.sort_order), -1)).where(
        WorkingSetItem.set_id == set_id
    )
    current_max_order = (await db.execute(max_order_stmt)).scalar_one()

    # Validate that records exist in the model
    model = _RECORD_MODELS.get(ws.record_type)
    if not model:
        raise HTTPException(status_code=400, detail=f"Unbekannter Datensatztyp {ws.record_type}")

    new_items_to_add: list[WorkingSetItem] = []
    order = current_max_order + 1

    for it in items:
        if it.record_id in existing_ids:
            continue

        item_sort_order = it.sort_order if it.sort_order != 0 else order
        new_items_to_add.append(
            WorkingSetItem(
                set_id=set_id,
                record_id=it.record_id,
                sort_order=item_sort_order,
                note=it.note,
                created_at=_now(),
            )
        )
        existing_ids.add(it.record_id)
        order += 1

    if new_items_to_add:
        db.add_all(new_items_to_add)
        ws.updated_at = _now()
        await db.commit()

    detail = await get_working_set_detail(db, set_id, user)
    return detail.items


async def update_working_set_item(
    db: AsyncSession,
    set_id: uuid.UUID,
    item_id: uuid.UUID,
    data: WorkingSetItemUpdate,
    user: User,
) -> WorkingSetItemRead:
    ws = await db.get(WorkingSet, set_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Arbeitsliste nicht gefunden.")

    _check_set_access(ws, user)

    item = await db.get(WorkingSetItem, item_id)
    if not item or item.set_id != set_id:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden.")

    if data.sort_order is not None:
        item.sort_order = data.sort_order
    if data.note is not None:
        item.note = data.note

    ws.updated_at = _now()
    await db.commit()

    detail = await get_working_set_detail(db, set_id, user)
    for it in detail.items:
        if it.id == item_id:
            return it
    raise HTTPException(status_code=404, detail="Eintrag nicht gefunden.")


async def delete_working_set_item(
    db: AsyncSession,
    set_id: uuid.UUID,
    item_id: uuid.UUID,
    user: User,
) -> None:
    ws = await db.get(WorkingSet, set_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Arbeitsliste nicht gefunden.")

    _check_set_access(ws, user)

    item = await db.get(WorkingSetItem, item_id)
    if not item or item.set_id != set_id:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden.")

    await db.delete(item)
    ws.updated_at = _now()
    await db.commit()


async def reorder_working_set_items(
    db: AsyncSession,
    set_id: uuid.UUID,
    item_ids: list[uuid.UUID],
    user: User,
) -> None:
    ws = await db.get(WorkingSet, set_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Arbeitsliste nicht gefunden.")

    _check_set_access(ws, user)

    items_stmt = select(WorkingSetItem).where(WorkingSetItem.set_id == set_id)
    items = {item.id: item for item in (await db.execute(items_stmt)).scalars().all()}

    for index, item_id in enumerate(item_ids):
        item = items.get(item_id)
        if item:
            item.sort_order = index

    ws.updated_at = _now()
    await db.commit()
