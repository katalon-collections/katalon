# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from katalon.core.dependencies import CurrentUser, DBDep
from katalon.core.schemas import RECORD_TYPES
from katalon.services.presence_service import (
    get_active_presences,
    get_active_presences_batch,
    heartbeat,
    release,
)

router = APIRouter(prefix="/presence", tags=["presence"])


def _validate_resource_type(resource_type: str) -> None:
    if resource_type not in RECORD_TYPES:
        raise HTTPException(status_code=422, detail=f"Ungültiger Datensatztyp '{resource_type}'.")


class HeartbeatRequest(BaseModel):
    session_id: str


class ActivePresenceRead(BaseModel):
    user_id: uuid.UUID
    user_email: str
    since: datetime


class BatchPresenceRequest(BaseModel):
    resource_type: str
    resource_ids: list[uuid.UUID]


@router.post("/{resource_type}/{resource_id}/heartbeat", response_model=list[ActivePresenceRead])
async def send_heartbeat(
    resource_type: str,
    resource_id: uuid.UUID,
    data: HeartbeatRequest,
    db: DBDep,
    current_user: CurrentUser,
) -> list[ActivePresenceRead]:
    _validate_resource_type(resource_type)
    await heartbeat(db, resource_type, resource_id, current_user.id, data.session_id)
    others = await get_active_presences(db, resource_type, resource_id, exclude_user_id=current_user.id)
    return [ActivePresenceRead(user_id=p.user_id, user_email=p.user_email, since=p.since) for p in others]


@router.delete("/{resource_type}/{resource_id}", status_code=204)
async def release_presence(
    resource_type: str,
    resource_id: uuid.UUID,
    db: DBDep,
    _: CurrentUser,
    session_id: str = Query(...),
) -> None:
    _validate_resource_type(resource_type)
    await release(db, resource_type, resource_id, session_id)


@router.get("/{resource_type}/{resource_id}", response_model=list[ActivePresenceRead])
async def list_presence(
    resource_type: str, resource_id: uuid.UUID, db: DBDep, current_user: CurrentUser
) -> list[ActivePresenceRead]:
    _validate_resource_type(resource_type)
    others = await get_active_presences(db, resource_type, resource_id, exclude_user_id=current_user.id)
    return [ActivePresenceRead(user_id=p.user_id, user_email=p.user_email, since=p.since) for p in others]


@router.post("/batch", response_model=dict[uuid.UUID, list[ActivePresenceRead]])
async def list_presence_batch(
    data: BatchPresenceRequest, db: DBDep, current_user: CurrentUser
) -> dict[uuid.UUID, list[ActivePresenceRead]]:
    _validate_resource_type(data.resource_type)
    by_resource = await get_active_presences_batch(db, data.resource_type, data.resource_ids)
    return {
        resource_id: [
            ActivePresenceRead(user_id=p.user_id, user_email=p.user_email, since=p.since)
            for p in presences
            if p.user_id != current_user.id
        ]
        for resource_id, presences in by_resource.items()
    }
