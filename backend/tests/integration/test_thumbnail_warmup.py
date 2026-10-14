# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Thumbnail warm-up: which media are warmed, order, throttling, resumable chain."""

from __future__ import annotations

import asyncio
import threading
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from katalon.core.thumbnails import THUMBNAIL_HEIGHTS


@pytest.fixture
def warm_env(migrated_database: str, monkeypatch: pytest.MonkeyPatch, fake_reindex_redis: Any):
    import katalon.config as config
    from katalon.integrations import cantaloupe
    from katalon.workers import thumbnail_tasks

    monkeypatch.setattr(config.settings, "database_url", migrated_database)
    monkeypatch.setattr(config.settings, "thumbnail_warm_batch_size", 2)
    monkeypatch.setattr(config.settings, "thumbnail_warm_concurrency", 2)

    env: dict[str, Any] = {"calls": [], "active": 0, "peak": 0, "queue": []}

    async def fake_fetch(client: Any, identifier: str, height: int) -> bool:
        env["active"] += 1
        env["peak"] = max(env["peak"], env["active"])
        await asyncio.sleep(0.005)
        env["active"] -= 1
        env["calls"].append((identifier, height))
        return not identifier.startswith("broken")

    monkeypatch.setattr(cantaloupe, "fetch_derivative", fake_fetch)
    monkeypatch.setattr(
        thumbnail_tasks, "enqueue", lambda task, *a, **k: env["queue"].append((task, a, k))
    )
    return env


def _drain(env: dict[str, Any], limit: int = 1000) -> None:
    for _ in range(limit):
        if not env["queue"]:
            return
        task, args, kwargs = env["queue"].pop(0)
        task.run(*args, **kwargs)
    raise AssertionError("warm-up chain did not finish")


def _insert_media(database_url: str, specs: list[dict[str, Any]]) -> list[str]:
    """Insert one public object with the given media rows; returns their storage keys."""
    from katalon.core.models import MediaFile, Object

    async def run() -> list[str]:
        engine = create_async_engine(database_url, poolclass=NullPool)
        try:
            async with async_sessionmaker(engine, class_=AsyncSession)() as session:
                obj = Object(idno=f"TW-{uuid.uuid4().hex[:10]}", status="public", metadata_={})
                session.add(obj)
                await session.flush()
                keys = []
                for spec in specs:
                    key = spec.get("key") or f"tw/{uuid.uuid4().hex}.tif"
                    session.add(MediaFile(
                        object_id=obj.id,
                        filename=key,
                        storage_key=key,
                        mime_type=spec.get("mime", "image/tiff"),
                        status=spec.get("status", "ready"),
                        is_primary=spec.get("primary", False),
                        is_public=spec.get("public", True),
                        deleted_at=datetime.now(UTC).replace(tzinfo=None) if spec.get("deleted") else None,
                    ))
                    keys.append(key)
                await session.commit()
                return keys
        finally:
            await engine.dispose()

    return asyncio.run(run())


def _encoded(key: str) -> str:
    from katalon.core.media_storage import iiif_identifier

    return iiif_identifier(None, key)


def test_bulk_warms_ready_images_primary_first_throttled(warm_env: dict[str, Any], migrated_database: str) -> None:
    from katalon.workers import thumbnail_tasks

    keys = _insert_media(migrated_database, [
        {"primary": False}, {"primary": True}, {"primary": False, "public": False},
        {"primary": True, "status": "pending"}, {"primary": False, "deleted": True},
        {"primary": False, "mime": "application/pdf"},
    ])
    rest, primary, internal, pending, deleted, pdf = (_encoded(k) for k in keys)

    state = thumbnail_tasks.start_bulk_sync()
    assert state["running"] is True and state["phase"] == "primary"
    _drain(warm_env)

    warmed = [identifier for identifier, _ in warm_env["calls"]]
    # Every size of every ready image, internal ones included (admins view them too).
    for identifier in (primary, rest, internal):
        assert {h for i, h in warm_env["calls"] if i == identifier} == set(THUMBNAIL_HEIGHTS)
    for identifier in (pending, deleted, pdf):
        assert identifier not in warmed
    # Primary images of the whole holding come before any other image.
    assert warmed.index(primary) < warmed.index(rest)
    assert warm_env["peak"] <= 2

    final = thumbnail_tasks.bulk_status()
    assert final["phase"] == "done" and final["running"] is False
    assert final["done"] + final["failed"] == final["total"]


def test_primary_only_stops_after_primary_phase(warm_env: dict[str, Any], migrated_database: str) -> None:
    from katalon.workers import thumbnail_tasks

    rest, primary = (_encoded(k) for k in _insert_media(migrated_database, [{}, {"primary": True}]))
    thumbnail_tasks.start_bulk_sync(primary_only=True, restart=True)
    _drain(warm_env)
    warmed = {identifier for identifier, _ in warm_env["calls"]}
    assert primary in warmed and rest not in warmed
    assert thumbnail_tasks.bulk_status()["phase"] == "done"


def test_running_chain_is_not_started_twice_and_interrupted_run_resumes(
    warm_env: dict[str, Any], migrated_database: str, fake_reindex_redis: Any
) -> None:
    import fakeredis

    from katalon.workers import thumbnail_tasks

    _insert_media(migrated_database, [{"primary": True}, {"primary": True}, {"primary": True}])
    thumbnail_tasks.start_bulk_sync(restart=True)
    assert len(warm_env["queue"]) == 1
    # A second start while the chain runs only reports progress.
    assert thumbnail_tasks.start_bulk_sync()["running"] is True
    assert len(warm_env["queue"]) == 1

    # One batch runs, then the worker dies: queued follow-up lost, lease expires.
    task, args, kwargs = warm_env["queue"].pop(0)
    task.run(*args, **kwargs)
    warm_env["queue"].clear()
    fakeredis.FakeRedis(server=fake_reindex_redis).delete(thumbnail_tasks.LEASE_KEY)
    first_batch = list(warm_env["calls"])

    resumed = thumbnail_tasks.start_bulk_sync()
    assert resumed["done"] > 0
    _drain(warm_env)
    later = warm_env["calls"][len(first_batch):]
    # Nothing of the first batch is warmed again.
    assert not {i for i, _ in first_batch} & {i for i, _ in later}


def test_restart_supersedes_old_chain(warm_env: dict[str, Any], migrated_database: str) -> None:
    from katalon.workers import thumbnail_tasks

    _insert_media(migrated_database, [{"primary": True}])
    thumbnail_tasks.start_bulk_sync(restart=True)
    old_task, old_args, _ = warm_env["queue"].pop(0)
    from katalon.workers import reindex_state

    reindex_state.redis_client().delete(thumbnail_tasks.LEASE_KEY)
    thumbnail_tasks.start_bulk_sync(restart=True)
    assert old_task.run(*old_args) == {"status": "superseded"}


def test_single_media_warm_skips_unready(warm_env: dict[str, Any], migrated_database: str) -> None:
    from katalon.core.models import MediaFile
    from katalon.workers import thumbnail_tasks

    ready, pending = _insert_media(migrated_database, [{}, {"status": "pending"}])

    async def ids() -> list[str]:
        from sqlalchemy import select

        engine = create_async_engine(migrated_database, poolclass=NullPool)
        try:
            async with async_sessionmaker(engine, class_=AsyncSession)() as session:
                rows = await session.execute(
                    select(MediaFile.id).where(MediaFile.storage_key.in_([ready, pending]))
                )
                return [str(i) for i in rows.scalars()]
        finally:
            await engine.dispose()

    result = thumbnail_tasks.warm_thumbnails.run(asyncio.run(ids()))
    assert result == {"warmed": 1, "failed": 0}
    assert {i for i, _ in warm_env["calls"]} == {_encoded(ready)}


@pytest.mark.asyncio
async def test_admin_endpoints_require_admin(async_client, auth_headers, fake_reindex_redis, monkeypatch) -> None:
    from katalon.workers import thumbnail_tasks

    monkeypatch.setattr(thumbnail_tasks, "enqueue", lambda *a, **k: None)
    assert (await async_client.post("/v1/admin/thumbnails/warm")).status_code == 401
    response = await async_client.post(
        "/v1/admin/thumbnails/warm", headers=auth_headers, json={"primary_only": True, "restart": True}
    )
    assert response.status_code == 202, response.text
    assert response.json()["running"] is True and response.json()["primary_only"] is True
    status = await async_client.get("/v1/admin/thumbnails/warm", headers=auth_headers)
    assert status.json()["phase"] == "primary"


@pytest.mark.asyncio
async def test_concurrent_starts_initialize_and_enqueue_only_once(warm_env, monkeypatch) -> None:
    from katalon.workers import thumbnail_tasks

    entered, release = asyncio.Event(), asyncio.Event()

    async def slow_count(*_args):
        entered.set()
        await release.wait()
        return 10

    monkeypatch.setattr(thumbnail_tasks, "_count_images", slow_count)
    first = asyncio.create_task(thumbnail_tasks.start_bulk(None, restart=True))
    await entered.wait()
    try:
        assert (await thumbnail_tasks.start_bulk(None, restart=True))["running"] is True
        assert warm_env["queue"] == []
    finally:
        release.set()
    assert (await first)["total"] == 10
    assert len(warm_env["queue"]) == 1


def test_long_batch_cannot_be_restarted_or_processed_twice(
    warm_env, migrated_database, monkeypatch, fake_reindex_redis
) -> None:
    from concurrent.futures import ThreadPoolExecutor

    import fakeredis

    from katalon.workers import thumbnail_tasks

    _insert_media(migrated_database, [{"primary": True}])
    monkeypatch.setattr(thumbnail_tasks, "LEASE_TTL_SECONDS", 1)
    entered, release = threading.Event(), threading.Event()

    async def slow_warm(identifiers):
        entered.set()
        assert await asyncio.to_thread(release.wait, 5)
        return len(identifiers), 0

    monkeypatch.setattr(thumbnail_tasks, "warm_identifiers", slow_warm)
    thumbnail_tasks.start_bulk_sync(restart=True)
    task, args, _ = warm_env["queue"].pop(0)
    with ThreadPoolExecutor(max_workers=1) as pool:
        job = pool.submit(task.run, *args)
        assert entered.wait(5)
        try:
            time.sleep(1.3)
            client = fakeredis.FakeRedis(server=fake_reindex_redis, decode_responses=True)
            assert not client.exists(thumbnail_tasks.LEASE_KEY)
            assert client.exists(thumbnail_tasks.LOCK_KEY)
            assert thumbnail_tasks.start_bulk_sync(restart=True)["running"] is True
            assert task.run(*args) == {"status": "busy"}
            assert warm_env["queue"] == []
        finally:
            release.set()
        assert job.result(timeout=5)["status"] == "batch"
    assert thumbnail_tasks.bulk_status()["done"] >= 1
    assert len(warm_env["queue"]) == 1
