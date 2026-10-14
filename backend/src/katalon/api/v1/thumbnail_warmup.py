# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Admin control of the thumbnail warm-up (workers/thumbnail_tasks.py)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from katalon.core.dependencies import DBDep, require_role

router = APIRouter(prefix="/admin/thumbnails", tags=["admin"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"description": "Missing, invalid, or expired credentials"},
    403: {"description": "Insufficient permissions"},
    503: {"description": "Redis unavailable"},
}


class WarmRequest(BaseModel):
    primary_only: bool = False
    restart: bool = False


class WarmStatus(BaseModel):
    running: bool
    phase: Literal["primary", "rest", "done"] | None = None
    primary_only: bool | None = None
    done: int | None = None
    failed: int | None = None
    total: int | None = None
    started_at: str | None = None
    updated_at: str | None = None
    finished_at: str | None = None


def _status(state: dict[str, Any]) -> WarmStatus:
    return WarmStatus.model_validate({k: v for k, v in state.items() if k in WarmStatus.model_fields})


@router.get("/warm", response_model=WarmStatus, dependencies=[require_role("admin")],
            summary="Progress of the bulk thumbnail warm-up", responses=_ERRORS)
async def get_warm_status() -> WarmStatus:
    from katalon.workers.thumbnail_tasks import bulk_status

    try:
        return _status(bulk_status())
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Redis nicht erreichbar") from exc


@router.post("/warm", response_model=WarmStatus, status_code=202, dependencies=[require_role("admin")],
             summary="Pre-render all thumbnails (primary images first); resumes an interrupted run",
             responses=_ERRORS)
async def start_warm(db: DBDep, body: WarmRequest | None = None) -> WarmStatus:
    from katalon.workers.thumbnail_tasks import start_bulk

    request = body or WarmRequest()
    try:
        state = await start_bulk(db, primary_only=request.primary_only, restart=request.restart)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Redis nicht erreichbar") from exc
    return _status(state)
