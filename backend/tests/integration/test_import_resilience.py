# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Import-task resilience tests (katalon issue #382).

``import_records_task`` runs the whole CSV/Excel import inside a single
SQLAlchemy transaction that is committed exactly once, after every row has
been processed (see ``katalon/workers/import_tasks.py``). These tests prove
the resulting invariant: any failure before that final commit — a worker
crash, a dropped DB connection, an unexpected exception — must not leave a
half-imported batch in the database. There is no per-row commit to roll back
partially, so "the worker died mid-import" and "a DB call raised" produce the
identical, already-tested code path exercised here.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest
import sqlalchemy.ext.asyncio as sa_asyncio
from sqlalchemy import select

from katalon.core.models import Object


class _FakeRedis:
    """Stand-in for redis.from_url — the import task's cancel-check only calls .get()."""

    def get(self, key: str) -> None:
        return None


def _patch_no_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    from katalon.workers.import_tasks import import_records_task

    monkeypatch.setattr("redis.from_url", lambda *args, **kwargs: _FakeRedis())
    monkeypatch.setattr(import_records_task, "update_state", lambda **kwargs: None)


def _fail_flush_after(monkeypatch: pytest.MonkeyPatch, fail_at_call: int) -> None:
    """Make the Nth AsyncSession.flush() call raise, simulating a dropped DB
    connection or the worker process being killed at that point."""
    original_flush = sa_asyncio.AsyncSession.flush
    call_count = {"n": 0}

    async def flaky_flush(self: Any, *args: Any, **kwargs: Any) -> None:
        call_count["n"] += 1
        if call_count["n"] == fail_at_call:
            raise ConnectionError("simulated DB connection drop")
        return await original_flush(self, *args, **kwargs)

    monkeypatch.setattr(sa_asyncio.AsyncSession, "flush", flaky_flush)


@pytest.mark.asyncio
async def test_import_failure_mid_batch_leaves_no_partial_records(
    app, monkeypatch: pytest.MonkeyPatch
) -> None:
    from katalon.database import AsyncSessionLocal
    from katalon.workers.import_tasks import import_records_task

    _patch_no_broker(monkeypatch)
    # 5 rows create 5 flushes (one per new record); fail on the 3rd so two
    # records would already be flushed (visible in-transaction) when the
    # error hits — the assertion below proves that visibility does not
    # survive because the batch never reaches its single final commit().
    _fail_flush_after(monkeypatch, fail_at_call=3)

    marker = f"IMPORT-CRASH-{uuid.uuid4().hex}"
    rows = [{"title": f"{marker} row {i}"} for i in range(5)]

    with pytest.raises(ConnectionError):
        await asyncio.to_thread(
            import_records_task.run,
            "object",
            rows,
            {"title": "label"},
        )

    async with AsyncSessionLocal() as session:
        persisted = (
            await session.execute(
                select(Object).where(Object.metadata_["label"].astext.like(f"{marker}%"))
            )
        ).scalars().all()
        assert persisted == []


@pytest.mark.asyncio
async def test_import_failure_reports_error_result_and_failure_notification(
    app, monkeypatch: pytest.MonkeyPatch
) -> None:
    from katalon.workers import import_tasks
    from katalon.workers.import_tasks import import_records_task

    _patch_no_broker(monkeypatch)
    _fail_flush_after(monkeypatch, fail_at_call=1)

    enqueued: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        import_tasks, "enqueue", lambda *args, **kwargs: enqueued.append(args)
    )

    with pytest.raises(ConnectionError):
        await asyncio.to_thread(
            import_records_task.run,
            "object",
            [{"title": "irrelevant"}],
            {"title": "label"},
            user_id=str(uuid.uuid4()),
        )

    assert len(enqueued) == 1
    _, user_id, subject, _text = enqueued[0]
    assert subject == "Katalon: Import fehlgeschlagen"
