# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Broker-tolerant Celery enqueue helpers (#274)."""
import pytest
from fastapi import HTTPException

from katalon.workers.enqueue import enqueue, enqueue_or_503


class _OkTask:
    name = "ok"

    def delay(self, *args, **kwargs):
        class _R:
            id = "tid-1"
        return _R()


class _BrokenTask:
    name = "broken"

    def delay(self, *args, **kwargs):
        raise ConnectionError("broker down")


def test_enqueue_returns_id_on_success() -> None:
    assert enqueue(_OkTask()) == "tid-1"


def test_enqueue_swallows_broker_error() -> None:
    # A broker outage must not break the request path — returns None, no raise.
    assert enqueue(_BrokenTask()) is None


def test_enqueue_or_503_returns_id() -> None:
    assert enqueue_or_503(_OkTask()) == "tid-1"


def test_enqueue_or_503_raises_503_on_broker_error() -> None:
    with pytest.raises(HTTPException) as exc:
        enqueue_or_503(_BrokenTask())
    assert exc.value.status_code == 503


class _CountingTask:
    """Fake Celery task recording every dispatched call."""

    name = "counting"

    def __init__(self) -> None:
        self.calls: list[tuple[tuple, dict]] = []

    def delay(self, *args, **kwargs):
        self.calls.append((args, kwargs))

        class _R:
            id = "tid-2"
        return _R()


class _FakeSession:
    """Duck-typed stand-in for AsyncSession — after_commit only touches `.info`."""

    def __init__(self) -> None:
        self.info: dict = {}


@pytest.mark.asyncio
async def test_after_commit_defers_dispatch_until_drained() -> None:
    from katalon.workers.enqueue import after_commit, run_after_commit_hooks

    db = _FakeSession()
    task = _CountingTask()
    after_commit(db, task, "object", "id-1")
    assert task.calls == []  # not dispatched yet — no commit observed

    await run_after_commit_hooks(db)
    assert task.calls == [(("object", "id-1"), {})]


@pytest.mark.asyncio
async def test_after_commit_hooks_drain_exactly_once() -> None:
    from katalon.workers.enqueue import after_commit, run_after_commit_hooks

    db = _FakeSession()
    task = _CountingTask()
    after_commit(db, task, "x")
    await run_after_commit_hooks(db)
    await run_after_commit_hooks(db)  # e.g. a second commit later in the same request
    assert len(task.calls) == 1


@pytest.mark.asyncio
async def test_discard_after_commit_hooks_drops_without_dispatch() -> None:
    """Simulates a rollback: queued calls must never fire."""
    from katalon.workers.enqueue import (
        after_commit,
        discard_after_commit_hooks,
        run_after_commit_hooks,
    )

    db = _FakeSession()
    task = _CountingTask()
    after_commit(db, task, "object", "id-1")
    discard_after_commit_hooks(db)
    await run_after_commit_hooks(db)
    assert task.calls == []


@pytest.mark.asyncio
async def test_run_after_commit_hooks_is_noop_when_nothing_deferred() -> None:
    from katalon.workers.enqueue import run_after_commit_hooks

    await run_after_commit_hooks(_FakeSession())  # must not raise


@pytest.mark.asyncio
async def test_after_commit_broker_failure_at_drain_is_logged_not_raised() -> None:
    """A broker outage during the drain must not crash the request/task — matches
    the existing enqueue() swallow-and-log contract, just applied after commit."""
    from katalon.workers.enqueue import after_commit, run_after_commit_hooks

    db = _FakeSession()
    after_commit(db, _BrokenTask())
    await run_after_commit_hooks(db)  # must not raise

