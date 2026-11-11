# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Staff view of a record's anonymous view/download counters."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from katalon.core.dependencies import CurrentUser, DBDep, has_record_permission
from katalon.services import usage_service

router = APIRouter(prefix="/usage", tags=["usage"])


class UsageRead(BaseModel):
    enabled: bool
    views: int
    downloads: int
    views_30d: int
    downloads_30d: int


@router.get(
    "/{record_type}/{record_id}",
    response_model=UsageRead,
    summary="View/download counts of a record (all time and last 30 days)",
    responses={403: {"description": "Insufficient permissions"}},
)
async def get_usage(
    record_type: Literal["object", "entity", "place", "occurrence", "collection"],
    record_id: uuid.UUID,
    db: DBDep,
    current_user: CurrentUser,
) -> UsageRead:
    if not await has_record_permission(db, current_user, record_type, "read"):
        raise HTTPException(status_code=403, detail="Keine Leseberechtigung")
    enabled = await usage_service.usage_stats_enabled(db)
    return UsageRead(enabled=enabled, **await usage_service.totals(db, record_type, record_id))
