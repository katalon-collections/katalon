# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from katalon.core.dependencies import DBDep, require_role
from katalon.core.models import (
    Collection,
    Entity,
    Object,
    Occurrence,
    Place,
    Procedure,
    StorageLocation,
)
from katalon.integrations.elasticsearch import count_by_type, count_stale_export_contexts
from katalon.integrations.metadata_format import EXPORT_CONTEXT_VERSION
from katalon.services.export_context_service import EXPORT_CONTEXT_TYPES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/index-health", tags=["admin"])

_MODEL_MAP: dict[str, Any] = {
    "object": Object,
    "entity": Entity,
    "place": Place,
    "occurrence": Occurrence,
    "procedure": Procedure,
    "collection": Collection,
    "storage_location": StorageLocation,
}


class TypeHealth(BaseModel):
    db: int
    es: int
    delta: int


class IndexHealthResponse(BaseModel):
    types: dict[str, TypeHealth]
    # Index documents whose export context predates this Katalon version. OAI and
    # exports rebuild them from the database (slower) until a full reindex.
    stale_export_contexts: int = 0


@router.get(
    "",
    response_model=IndexHealthResponse,
    dependencies=[require_role("admin")],
    summary="Get record counts and DB/Elasticsearch sync deltas per record type",
    responses={
        401: {"description": "Missing, invalid, or expired credentials"},
        403: {"description": "Insufficient permissions"},
    },
)
async def get_index_health(db: DBDep) -> IndexHealthResponse:
    types: dict[str, TypeHealth] = {}
    for record_type, model in _MODEL_MAP.items():
        count_query = select(func.count()).select_from(model)
        if hasattr(model, "deleted_at"):
            count_query = count_query.where(model.deleted_at.is_(None))
        db_count = (await db.execute(count_query)).scalar_one()
        es_count = await count_by_type(record_type)
        types[record_type] = TypeHealth(db=db_count, es=es_count, delta=db_count - es_count)
    stale = await count_stale_export_contexts(EXPORT_CONTEXT_VERSION, EXPORT_CONTEXT_TYPES)
    return IndexHealthResponse(types=types, stale_export_contexts=stale)


@router.post(
    "/reconcile",
    dependencies=[require_role("admin")],
    summary="Trigger an asynchronous Elasticsearch reconciliation job",
    responses={
        400: {"description": "mode must be 'count' or 'id_diff'"},
        401: {"description": "Missing, invalid, or expired credentials"},
        403: {"description": "Insufficient permissions"},
        503: {"description": "Background task queue unavailable (broker down)"},
    },
)
async def trigger_reconciliation(mode: str = "id_diff") -> dict[str, str]:
    if mode not in ("count", "id_diff"):
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="mode must be 'count' or 'id_diff'")

    from katalon.workers.enqueue import enqueue_or_503
    from katalon.workers.index_tasks import reconciliation_job_task

    enqueue_or_503(reconciliation_job_task, mode=mode, force=True)
    return {"status": "started", "mode": mode}


status_router = APIRouter(prefix="/admin/index-status", tags=["admin"])


class ReindexTypeStatus(BaseModel):
    state: Literal["idle", "running", "done", "failed", "error"]
    queued: bool
    pending_changes: bool
    total: int | None = None
    built: int | None = None
    indexed: int | None = None
    removed: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    eta_seconds: int | None = None
    error: str | None = None


_STATES = {"idle", "running", "done", "failed", "error"}


class FullRebuildStatus(ReindexTypeStatus):
    """total/built count record types; current_type is the one being built."""

    current_type: str | None = None


class IndexStatusResponse(BaseModel):
    available: bool
    types: dict[str, ReindexTypeStatus]
    full_rebuild: FullRebuildStatus | None = None


def _opt_int(raw: dict[str, str], key: str) -> int | None:
    value = raw.get(key)
    return int(value) if value not in (None, "") else None


def _opt_dt(raw: dict[str, str], key: str) -> datetime | None:
    value = raw.get(key)
    return datetime.fromisoformat(value) if value else None


def _type_status(entry: dict[str, Any], now: datetime) -> ReindexTypeStatus:
    raw: dict[str, str] = entry["progress"]
    state = raw.get("state") or "idle"
    if state == "running" and not entry["locked"]:
        # Progress says running but the lease is gone: the worker died mid-run.
        state = "failed"
    status = ReindexTypeStatus(
        state=state if state in _STATES else "idle",
        queued=entry["queued"],
        pending_changes=entry["dirty"],
        total=_opt_int(raw, "total"),
        built=_opt_int(raw, "built"),
        indexed=_opt_int(raw, "indexed"),
        removed=_opt_int(raw, "removed"),
        started_at=_opt_dt(raw, "started_at"),
        finished_at=_opt_dt(raw, "finished_at"),
        error=raw.get("error") or None,
    )
    if status.state == "running" and status.started_at and status.total and status.built:
        elapsed = (now - status.started_at).total_seconds()
        status.eta_seconds = int(elapsed / status.built * (status.total - status.built))
    return status


@status_router.get(
    "",
    response_model=IndexStatusResponse,
    dependencies=[require_role("admin")],
    summary="Get running/queued bulk reindex jobs and their progress per record type",
    responses={
        401: {"description": "Missing, invalid, or expired credentials"},
        403: {"description": "Insufficient permissions"},
    },
)
async def get_index_status() -> IndexStatusResponse:
    from katalon.workers.reindex_state import FULL, read_status

    types = list(_MODEL_MAP)
    try:
        raw = await asyncio.to_thread(read_status, types)
    except Exception:
        logger.warning("index status unavailable (redis unreachable?)", exc_info=True)
        empty = ReindexTypeStatus(state="idle", queued=False, pending_changes=False)
        return IndexStatusResponse(available=False, types=dict.fromkeys(types, empty))
    now = datetime.now(UTC)
    full_raw = raw[FULL]
    full = FullRebuildStatus(
        **_type_status(full_raw, now).model_dump(),
        current_type=full_raw["progress"].get("current_type") or None,
    )
    return IndexStatusResponse(
        available=True,
        types={t: _type_status(raw[t], now) for t in types},
        full_rebuild=full,
    )
