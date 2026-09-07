# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from katalon.core.dependencies import CurrentUser, DBDep
from katalon.core.schemas import (
    WorkingSetAddItemsRequest,
    WorkingSetCreate,
    WorkingSetDetailRead,
    WorkingSetItemRead,
    WorkingSetItemUpdate,
    WorkingSetRead,
    WorkingSetReorderRequest,
    WorkingSetUpdate,
)
from katalon.services import working_set_service

router = APIRouter(prefix="/working-sets", tags=["working-sets"])


@router.get(
    "",
    response_model=list[WorkingSetRead],
    summary="List working sets visible to current user",
)
async def list_working_sets(
    db: DBDep,
    current_user: CurrentUser,
    record_type: str | None = Query(None, description="Filter by record type"),
    record_id: uuid.UUID | None = Query(None, description="Filter by contained record ID"),
) -> list[WorkingSetRead]:
    return await working_set_service.list_working_sets(
        db, current_user, record_type=record_type, record_id=record_id
    )


@router.post(
    "",
    response_model=WorkingSetRead,
    status_code=201,
    summary="Create a new working set",
)
async def create_working_set(
    data: WorkingSetCreate,
    db: DBDep,
    current_user: CurrentUser,
) -> WorkingSetRead:
    return await working_set_service.create_working_set(db, data, current_user)


@router.get(
    "/{set_id}",
    response_model=WorkingSetDetailRead,
    summary="Get working set details with enriched items",
)
async def get_working_set_detail(
    set_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentUser,
) -> WorkingSetDetailRead:
    return await working_set_service.get_working_set_detail(db, set_id, current_user)


@router.put(
    "/{set_id}",
    response_model=WorkingSetRead,
    summary="Update working set metadata",
)
async def update_working_set(
    set_id: uuid.UUID,
    data: WorkingSetUpdate,
    db: DBDep,
    current_user: CurrentUser,
) -> WorkingSetRead:
    return await working_set_service.update_working_set(db, set_id, data, current_user)


@router.delete(
    "/{set_id}",
    status_code=204,
    summary="Delete a working set",
)
async def delete_working_set(
    set_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentUser,
) -> None:
    await working_set_service.delete_working_set(db, set_id, current_user)


@router.post(
    "/{set_id}/items",
    response_model=list[WorkingSetItemRead],
    summary="Add items to a working set",
)
async def add_items_to_working_set(
    set_id: uuid.UUID,
    data: WorkingSetAddItemsRequest,
    db: DBDep,
    current_user: CurrentUser,
) -> list[WorkingSetItemRead]:
    return await working_set_service.add_items_to_working_set(db, set_id, data, current_user)


@router.put(
    "/{set_id}/items/{item_id}",
    response_model=WorkingSetItemRead,
    summary="Update a working set item (note, sort_order)",
)
async def update_working_set_item(
    set_id: uuid.UUID,
    item_id: uuid.UUID,
    data: WorkingSetItemUpdate,
    db: DBDep,
    current_user: CurrentUser,
) -> WorkingSetItemRead:
    return await working_set_service.update_working_set_item(db, set_id, item_id, data, current_user)


@router.delete(
    "/{set_id}/items/{item_id}",
    status_code=204,
    summary="Remove an item from a working set",
)
async def delete_working_set_item(
    set_id: uuid.UUID,
    item_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentUser,
) -> None:
    await working_set_service.delete_working_set_item(db, set_id, item_id, current_user)


@router.put(
    "/{set_id}/reorder",
    status_code=204,
    summary="Reorder items in a working set",
)
async def reorder_working_set_items(
    set_id: uuid.UUID,
    data: WorkingSetReorderRequest,
    db: DBDep,
    current_user: CurrentUser,
) -> None:
    await working_set_service.reorder_working_set_items(db, set_id, data.item_ids, current_user)
