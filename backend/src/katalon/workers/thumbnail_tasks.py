# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Pre-render portal thumbnails in Cantaloupe's derivative cache.

Cantaloupe renders a thumbnail from the (pyramid) TIFF on first request, which
costs 0.1–1 s per image; from its cache it answers in well under 100 ms. These
tasks request every thumbnail size once so the first portal visitor never pays
the rendering cost:

``katalon.media.warm_thumbnails``       given media files, right after processing
``katalon.media.warm_thumbnails_bulk``  the whole holding, primary images first

The bulk run is a chain of short batch tasks, never one long task: a long task
would outlive Redis' visibility timeout and be delivered twice. Each batch warms
``thumbnail_warm_batch_size`` media with ``thumbnail_warm_concurrency`` parallel
requests and enqueues the next batch; only one chain runs at a time, so the
run never uses more Cantaloupe cores than configured. Progress (phase + last
media id) lives in Redis, so an interrupted run resumes where it stopped.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from typing import Any

import httpx
from redis.exceptions import LockNotOwnedError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import katalon.config as config
from katalon.core.media_storage import iiif_identifier
from katalon.core.media_validation import ALLOWED_IMAGE_MIME
from katalon.core.thumbnails import THUMBNAIL_HEIGHTS
from katalon.workers import reindex_state
from katalon.workers.celery_app import celery_app
from katalon.workers.enqueue import enqueue

logger = logging.getLogger(__name__)

STATE_KEY = "katalon:thumbwarm:state"
# Held by the batch currently running; a start request while it exists only
# reports progress instead of starting a second chain.
LEASE_KEY = "katalon:thumbwarm:lease"
LOCK_KEY = "katalon:thumbwarm:lock"
LEASE_TTL_SECONDS = 600
STATE_TTL_SECONDS = 30 * 24 * 3600

PHASE_PRIMARY = "primary"
PHASE_REST = "rest"
PHASE_DONE = "done"


def _image_media_query() -> Any:
    from katalon.core.models import MediaFile

    return select(MediaFile.id, MediaFile.iiif_storage_key, MediaFile.storage_key).where(
        MediaFile.status == "ready",
        MediaFile.deleted_at.is_(None),
        MediaFile.mime_type.in_(sorted(ALLOWED_IMAGE_MIME)),
    )


async def _with_session[T](work: Any) -> T:
    engine = create_async_engine(config.settings.database_url, poolclass=NullPool)
    try:
        async with async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as session:
            result: T = await work(session)
            return result
    finally:
        await engine.dispose()


async def warm_identifiers(identifiers: list[str]) -> tuple[int, int]:
    """Request every thumbnail size of each identifier; returns (warmed, failed) media."""
    semaphore = asyncio.Semaphore(max(1, config.settings.thumbnail_warm_concurrency))
    timeout = httpx.Timeout(float(config.settings.cantaloupe_task_timeout))

    async with httpx.AsyncClient(timeout=timeout) as client:
        from katalon.integrations.cantaloupe import fetch_derivative

        async def warm_one(identifier: str) -> bool:
            ok = True
            for height in THUMBNAIL_HEIGHTS:
                async with semaphore:
                    ok = await fetch_derivative(client, identifier, height) and ok
            return ok

        results = await asyncio.gather(*(warm_one(i) for i in identifiers))
    warmed = sum(results)
    return warmed, len(results) - warmed


def _identifiers(rows: Any) -> list[str]:
    return [iiif_identifier(row.iiif_storage_key, row.storage_key) for row in rows]


@celery_app.task(name="katalon.media.warm_thumbnails", acks_late=False)
def warm_thumbnails(media_ids: list[str]) -> dict[str, int]:
    """Warm the thumbnails of specific media files (e.g. right after processing)."""
    from katalon.core.models import MediaFile

    ids = [uuid.UUID(media_id) for media_id in media_ids]

    async def run() -> tuple[int, int]:
        async def load(session: AsyncSession) -> list[str]:
            rows = (await session.execute(_image_media_query().where(MediaFile.id.in_(ids)))).all()
            return _identifiers(rows)

        identifiers: list[str] = await _with_session(load)
        return await warm_identifiers(identifiers) if identifiers else (0, 0)

    warmed, failed = asyncio.run(run())
    return {"warmed": warmed, "failed": failed}


# --- bulk run -----------------------------------------------------------------


def bulk_status(client: Any | None = None) -> dict[str, Any]:
    client = client or reindex_state.redis_client()
    state: dict[str, Any] = dict(client.hgetall(STATE_KEY) or {})
    state["running"] = bool(client.exists(LEASE_KEY) or client.exists(LOCK_KEY))
    for key in ("done", "failed", "total"):
        if key in state:
            state[key] = int(state[key])
    if "primary_only" in state:
        state["primary_only"] = state["primary_only"] == "1"
    return state


async def _count_images(session: AsyncSession, primary_only: bool) -> int:
    from katalon.core.models import MediaFile

    query = _image_media_query()
    if primary_only:
        query = query.where(MediaFile.is_primary.is_(True))
    return int((await session.execute(select(func.count()).select_from(query.subquery()))).scalar_one())


async def start_bulk(
    session: AsyncSession, *, primary_only: bool = False, restart: bool = False
) -> dict[str, Any]:
    """Start (or resume) the bulk warm-up; a running chain is left alone."""
    client = reindex_state.redis_client()
    lock = client.lock(LOCK_KEY, timeout=LEASE_TTL_SECONDS, thread_local=False)
    if not lock.acquire(blocking=False):
        return bulk_status(client)
    try:
        with reindex_state.LeaseWatchdog(
            lock, interval=min(reindex_state.LOCK_RENEW_SECONDS, LEASE_TTL_SECONDS / 3)
        ):
            state = bulk_status(client)
            if client.exists(LEASE_KEY):
                return state
            resumable = state.get("phase") in (PHASE_PRIMARY, PHASE_REST)
            if restart or not resumable:
                total = await _count_images(session, primary_only)
                if not lock.owned():
                    raise RuntimeError("Thumbnail start lost its lock")
                client.delete(STATE_KEY)
                client.hset(STATE_KEY, mapping={
                    "run_id": uuid.uuid4().hex,
                    "phase": PHASE_PRIMARY,
                    "after_id": "",
                    "primary_only": "1" if primary_only else "0",
                    "done": 0,
                    "failed": 0,
                    "total": total,
                    "started_at": reindex_state.now_iso(),
                })
                client.expire(STATE_KEY, STATE_TTL_SECONDS)
            run_id = client.hget(STATE_KEY, "run_id")
            client.set(LEASE_KEY, run_id, ex=LEASE_TTL_SECONDS)
    finally:
        with contextlib.suppress(LockNotOwnedError):
            lock.release()
    # Release the lock before dispatch: a fast worker must be able to acquire it.
    enqueue(warm_thumbnails_bulk, run_id)
    return bulk_status(client)


def start_bulk_sync(*, primary_only: bool = False, restart: bool = False) -> dict[str, Any]:
    """CLI entry point (katalon-manage warm-thumbnails)."""
    result: dict[str, Any] = asyncio.run(
        _with_session(lambda s: start_bulk(s, primary_only=primary_only, restart=restart))
    )
    return result


async def _next_batch(session: AsyncSession, phase: str, after_id: str, limit: int) -> list[Any]:
    from katalon.core.models import MediaFile

    query = _image_media_query().where(MediaFile.is_primary.is_(phase == PHASE_PRIMARY))
    if after_id:
        query = query.where(MediaFile.id > uuid.UUID(after_id))
    return list((await session.execute(query.order_by(MediaFile.id).limit(limit))).all())


@celery_app.task(name="katalon.media.warm_thumbnails_bulk", acks_late=False)
def warm_thumbnails_bulk(run_id: str) -> dict[str, Any]:
    """Warm one batch of the bulk run and enqueue the next one."""
    client = reindex_state.redis_client()
    lock = client.lock(LOCK_KEY, timeout=LEASE_TTL_SECONDS, thread_local=False)
    if not lock.acquire(blocking=False):
        return {"status": "busy"}
    try:
        with reindex_state.LeaseWatchdog(
            lock, interval=min(reindex_state.LOCK_RENEW_SECONDS, LEASE_TTL_SECONDS / 3)
        ):
            result = _warm_bulk_batch(client, run_id, lock)
    finally:
        with contextlib.suppress(LockNotOwnedError):
            lock.release()
    if result["status"] in ("batch", "next_phase"):
        enqueue(warm_thumbnails_bulk, run_id)
    return result


def _warm_bulk_batch(client: Any, run_id: str, lock: Any) -> dict[str, Any]:
    state = client.hgetall(STATE_KEY) or {}
    if state.get("run_id") != run_id or state.get("phase") not in (PHASE_PRIMARY, PHASE_REST):
        return {"status": "superseded"}
    client.set(LEASE_KEY, run_id, ex=LEASE_TTL_SECONDS)

    phase = state["phase"]
    rows: list[Any] = asyncio.run(_with_session(
        lambda s: _next_batch(s, phase, state.get("after_id", ""), config.settings.thumbnail_warm_batch_size)
    ))
    if not lock.owned():
        raise RuntimeError("Thumbnail batch lost its lock")
    if not rows:
        if phase == PHASE_PRIMARY and state.get("primary_only") != "1":
            client.hset(STATE_KEY, mapping={"phase": PHASE_REST, "after_id": ""})
            client.set(LEASE_KEY, run_id, ex=LEASE_TTL_SECONDS)
            return {"status": "next_phase"}
        client.hset(STATE_KEY, mapping={"phase": PHASE_DONE, "finished_at": reindex_state.now_iso()})
        client.delete(LEASE_KEY)
        return {"status": "finished"}

    warmed, failed = asyncio.run(warm_identifiers(_identifiers(rows)))
    if not lock.owned():
        raise RuntimeError("Thumbnail batch lost its lock")
    # A restart while this batch ran replaced the state: do not overwrite it.
    if client.hget(STATE_KEY, "run_id") != run_id:
        return {"status": "superseded"}
    client.hincrby(STATE_KEY, "done", warmed)
    client.hincrby(STATE_KEY, "failed", failed)
    client.hset(STATE_KEY, mapping={"after_id": str(rows[-1].id), "updated_at": reindex_state.now_iso()})
    client.set(LEASE_KEY, run_id, ex=LEASE_TTL_SECONDS)
    return {"status": "batch", "warmed": warmed, "failed": failed}
