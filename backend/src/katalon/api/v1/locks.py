# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Manual Exclusive Lock API — set, release, force-unlock, and query locks."""

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from katalon.core.dependencies import (
    CurrentUser,
    DBDep,
    require_feature,
    require_role,
)
from katalon.core.models import User
from katalon.core.schemas import RECORD_TYPES
from katalon.services.lock_service import LockInfo, force_unlock, get_lock, get_locks_batch, release_lock, set_lock
from katalon.services.audit_service import log_change

router = APIRouter(prefix="/locks", tags=["locks"])


class LockCreate(BaseModel):
    resource_type: str = Field(..., description="e.g. object, entity, place, …")
    resource_id: uuid.UUID
    reason: str = Field(default="", max_length=256)
    expires_at: datetime | None = None


class LockRead(BaseModel):
    resource_type: str
    resource_id: str
    locked_by: str
    locked_by_email: str
    locked_at: datetime
    expires_at: datetime | None = None
    reason: str = ""


class BatchLockRequest(BaseModel):
    resource_type: str
    resource_ids: list[uuid.UUID]


def _validate_resource_type(resource_type: str) -> None:
    if resource_type not in RECORD_TYPES:
        raise HTTPException(status_code=422, detail=f"Ungültiger Datensatztyp '{resource_type}'.")


@router.post(
    "",
    response_model=LockRead,
    status_code=201,
    summary="Set a manual lock on a record",
    responses={
        409: {"description": "Resource is already locked by another user"},
        403: {"description": "Insufficient permissions"},
    },
)
async def create_lock(
    data: LockCreate, db: DBDep, current_user: CurrentUser, _: User = require_feature("manual_lock")
) -> LockRead:
    _validate_resource_type(data.resource_type)
    info = await set_lock(db, data.resource_type, data.resource_id, current_user, reason=data.reason, expires_at=data.expires_at)
    await log_change(db, record_type=data.resource_type, record_id=data.resource_id, user_id=current_user.id, action="lock_set", changed_fields={"reason": data.reason})
    await db.commit()
    return _to_read(data.resource_type, str(data.resource_id), info)


@router.delete(
    "/{resource_type}/{resource_id}",
    status_code=204,
    summary="Release own lock on a record",
    responses={
        403: {"description": "Not the lock owner"},
        404: {"description": "No lock found"},
    },
)
async def delete_lock(resource_type: str, resource_id: uuid.UUID, db: DBDep, current_user: CurrentUser) -> None:
    released = await release_lock(db, resource_type, resource_id, current_user)
    if not released:
        raise HTTPException(status_code=404, detail="Keine Sperre gefunden")
    await log_change(db, record_type=resource_type, record_id=resource_id, user_id=current_user.id, action="lock_released", changed_fields={})
    await db.commit()


@router.post(
    "/{resource_type}/{resource_id}/force-unlock",
    status_code=204,
    summary="Force-unlock a record (admin/superuser only)",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "No lock found"},
    },
)
async def force_unlock_endpoint(
    resource_type: str, resource_id: uuid.UUID, db: DBDep, current_user: CurrentUser, _: User = require_role("admin")
) -> None:
    released = await force_unlock(db, resource_type, resource_id, current_user)
    if not released:
        raise HTTPException(status_code=404, detail="Keine Sperre gefunden")
    await log_change(db, record_type=resource_type, record_id=resource_id, user_id=current_user.id, action="lock_force_unlock", changed_fields={})
    await db.commit()


@router.post(
    "/batch",
    response_model=dict[str, LockRead],
    summary="Batch-get locks for multiple records of the same type",
)
async def batch_get_locks(data: BatchLockRequest, db: DBDep, current_user: CurrentUser) -> dict[str, LockRead]:
    _validate_resource_type(data.resource_type)
    info_map = await get_locks_batch(db, data.resource_type, data.resource_ids)
    return {
        str(rid): LockRead(
            resource_type=data.resource_type,
            resource_id=str(rid),
            locked_by=str(info.locked_by),
            locked_by_email=info.locked_by_email,
            locked_at=info.locked_at,
            expires_at=info.expires_at,
            reason=info.reason,
        )
        for rid, info in info_map.items()
    }


@router.get(
    "/{resource_type}/{resource_id}",
    response_model=LockRead | None,
    summary="Get lock info for a record",
)
async def get_lock_endpoint(resource_type: str, resource_id: uuid.UUID, db: DBDep, current_user: CurrentUser) -> LockRead | None:
    _validate_resource_type(resource_type)
    info = await get_lock(db, resource_type, resource_id)
    if not info:
        return None
    return _to_read(resource_type, str(resource_id), info)


def _to_read(resource_type: str, resource_id: str, info: LockInfo) -> LockRead:
    return LockRead(
        resource_type=resource_type,
        resource_id=resource_id,
        locked_by=str(info.locked_by),
        locked_by_email=info.locked_by_email,
        locked_at=info.locked_at,
        expires_at=info.expires_at,
        reason=info.reason,
    )