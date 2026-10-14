# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Per-type reindex coordination: dedupe, follow-up, non-blocking lock, lease."""

import threading
import time
from typing import Any

import fakeredis
import pytest

from katalon.workers import index_tasks, reindex_state


@pytest.fixture
def redis_server(monkeypatch: pytest.MonkeyPatch) -> fakeredis.FakeServer:
    server = fakeredis.FakeServer()
    monkeypatch.setattr(
        reindex_state,
        "redis_client",
        lambda: fakeredis.FakeRedis(server=server, decode_responses=True),
    )
    return server


@pytest.fixture
def enqueued(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Any, ...]]:
    calls: list[tuple[Any, ...]] = []

    def fake_enqueue(_task: Any, *args: Any, **kwargs: Any) -> str:
        calls.append((*args, kwargs))
        return f"task-{len(calls)}"

    monkeypatch.setattr("katalon.workers.enqueue.enqueue", fake_enqueue)
    return calls


def _client(server: fakeredis.FakeServer) -> fakeredis.FakeRedis:
    return fakeredis.FakeRedis(server=server, decode_responses=True)


def test_burst_of_requests_enqueues_one_job(redis_server, enqueued) -> None:
    results = [reindex_state.request_bulk_reindex("object") for _ in range(50)]

    assert results.count(True) == 1
    assert enqueued == [("object", {"coalesce": True})]
    # Other types are independent.
    assert reindex_state.request_bulk_reindex("place") is True
    assert len(enqueued) == 2


def test_failed_enqueue_releases_queued_marker(redis_server, monkeypatch) -> None:
    monkeypatch.setattr("katalon.workers.enqueue.enqueue", lambda *_a, **_k: None)
    assert reindex_state.request_bulk_reindex("object") is False
    assert not _client(redis_server).exists(reindex_state.queued_key("object"))


def test_redis_outage_fails_open(monkeypatch, enqueued) -> None:
    def broken() -> Any:
        raise ConnectionError("redis down")

    monkeypatch.setattr(reindex_state, "redis_client", broken)
    assert reindex_state.request_bulk_reindex("object") is True
    assert len(enqueued) == 1


def _fake_stream(monkeypatch, *, started: threading.Event | None = None,
                 release: threading.Event | None = None) -> list[str]:
    runs: list[str] = []

    async def fake_stream(target_type: str, _progress: Any) -> dict[str, Any]:
        runs.append(target_type)
        if started is not None:
            started.set()
        if release is not None:
            assert release.wait(5)
        return {"status": "ok", "indexed": 0, "removed": 0, "target_type": target_type}

    monkeypatch.setattr(index_tasks, "_stream_reindex", fake_stream)
    return runs


def test_coalesced_job_skips_when_nothing_pending(redis_server, enqueued, monkeypatch) -> None:
    runs = _fake_stream(monkeypatch)
    reindex_state.request_bulk_reindex("object")

    first = index_tasks.bulk_reindex_type_task.run("object", coalesce=True)
    # A second (e.g. duplicate/expired-marker) message finds no pending change.
    second = index_tasks.bulk_reindex_type_task.run("object", coalesce=True)

    assert first["status"] == "ok"
    assert second["status"] == "skipped"
    assert runs == ["object"]
    progress = _client(redis_server).hgetall(reindex_state.progress_key("object"))
    assert progress["state"] == "done"


def test_changes_during_run_produce_exactly_one_follow_up(
    redis_server, enqueued, monkeypatch
) -> None:
    started, release = threading.Event(), threading.Event()
    runs = _fake_stream(monkeypatch, started=started, release=release)
    reindex_state.request_bulk_reindex("object")
    assert len(enqueued) == 1

    result: dict[str, Any] = {}
    worker = threading.Thread(
        target=lambda: result.update(
            index_tasks.bulk_reindex_type_task.run("object", coalesce=True)
        )
    )
    worker.start()
    assert started.wait(5)

    # 50 schema changes while the job runs: the first enqueues one waiting job,
    # the rest coalesce into it.
    for _ in range(50):
        reindex_state.request_bulk_reindex("object")
    assert len(enqueued) == 2

    # That waiting job is picked up by a second worker thread while the first
    # still runs: it must neither block nor run in parallel.
    t0 = time.monotonic()
    deferred = index_tasks.bulk_reindex_type_task.run("object", coalesce=True)
    assert deferred["status"] == "deferred"
    assert time.monotonic() - t0 < 1

    release.set()
    worker.join(5)
    assert result["status"] == "ok"
    # The finishing job saw pending changes and asked for exactly one follow-up.
    assert len(enqueued) == 3
    follow_up = index_tasks.bulk_reindex_type_task.run("object", coalesce=True)
    assert follow_up["status"] == "ok"
    assert runs == ["object", "object"]
    assert len(enqueued) == 3


def test_direct_call_while_running_marks_dirty(redis_server, enqueued, monkeypatch) -> None:
    started, release = threading.Event(), threading.Event()
    _fake_stream(monkeypatch, started=started, release=release)
    worker = threading.Thread(target=lambda: index_tasks.bulk_reindex_type_task.run("object"))
    worker.start()
    assert started.wait(5)

    assert index_tasks.bulk_reindex_type_task.run("object")["status"] == "deferred"
    release.set()
    worker.join(5)
    assert enqueued == [("object", {"coalesce": True})]


def test_crashed_worker_lock_expires_and_shutdown_releases(redis_server) -> None:
    client = _client(redis_server)
    stale = client.lock(reindex_state.RUN_LOCK_KEY, timeout=1, thread_local=False)
    assert stale.acquire(blocking=False)
    fresh = client.lock(reindex_state.RUN_LOCK_KEY, timeout=1, thread_local=False)
    assert not fresh.acquire(blocking=False)
    time.sleep(1.1)
    assert fresh.acquire(blocking=False)

    reindex_state.register_held_lock(fresh)
    reindex_state.release_all_held_locks()
    assert not client.exists(reindex_state.RUN_LOCK_KEY)


def test_watchdog_keeps_lease_alive(redis_server) -> None:
    client = _client(redis_server)
    lock = client.lock(reindex_state.RUN_LOCK_KEY, timeout=1, thread_local=False)
    assert lock.acquire(blocking=False)
    with reindex_state.LeaseWatchdog(lock, interval=0.3) as watchdog:
        time.sleep(1.5)
        assert client.exists(reindex_state.RUN_LOCK_KEY)
    assert not watchdog.lost
    lock.release()


def test_failed_run_records_error_and_releases_lock(redis_server, enqueued, monkeypatch) -> None:
    async def boom(_target_type: str, _progress: Any) -> dict[str, Any]:
        raise RuntimeError("es down")

    monkeypatch.setattr(index_tasks, "_stream_reindex", boom)
    with pytest.raises(RuntimeError):
        index_tasks.bulk_reindex_type_task.run("object")
    client = _client(redis_server)
    assert client.hgetall(reindex_state.progress_key("object"))["state"] == "failed"
    assert not client.exists(reindex_state.RUN_LOCK_KEY)


def test_rebuild_tasks_ack_early_to_avoid_redis_redelivery() -> None:
    # Redis redelivers unacked messages after its visibility timeout (1 h);
    # long rebuilds must not be started a second time while still running.
    assert index_tasks.bulk_reindex_type_task.acks_late is False
    assert index_tasks.reindex_all_task.acks_late is False


def test_failed_run_keeps_pending_marker_without_looping(
    redis_server, enqueued, monkeypatch
) -> None:
    async def boom(_target_type: str, _progress: Any) -> dict[str, Any]:
        raise RuntimeError("es down")

    monkeypatch.setattr(index_tasks, "_stream_reindex", boom)
    reindex_state.request_bulk_reindex("object")
    assert len(enqueued) == 1

    with pytest.raises(RuntimeError):
        index_tasks.bulk_reindex_type_task.run("object", coalesce=True)

    # No automatic retry loop …
    assert len(enqueued) == 1
    # … but the change is still pending and a worker (re)start picks it up.
    assert _client(redis_server).exists(reindex_state.dirty_key("object"))
    assert reindex_state.resubmit_pending(["object", "place"]) == ["object"]
    assert len(enqueued) == 2


def test_crashed_run_is_resubmitted_on_worker_start(redis_server, enqueued) -> None:
    # Simulates a worker killed mid-run: the message was acked at start,
    # the lease expired, the dirty marker is still there.
    reindex_state.request_bulk_reindex("object")
    _client(redis_server).delete(reindex_state.queued_key("object"))

    assert reindex_state.resubmit_pending(["object"]) == ["object"]
    # Nothing is resubmitted while a job for the type runs or waits.
    assert reindex_state.resubmit_pending(["object"]) == []


def test_successful_run_clears_marker(redis_server, enqueued, monkeypatch) -> None:
    _fake_stream(monkeypatch)
    reindex_state.request_bulk_reindex("object")
    index_tasks.bulk_reindex_type_task.run("object", coalesce=True)
    assert not _client(redis_server).exists(reindex_state.dirty_key("object"))
    assert reindex_state.resubmit_pending(["object"]) == []


def test_rebuilds_of_different_types_run_one_at_a_time(
    redis_server, enqueued, monkeypatch
) -> None:
    started, release = threading.Event(), threading.Event()
    runs = _fake_stream(monkeypatch, started=started, release=release)
    reindex_state.request_bulk_reindex("object")
    worker = threading.Thread(
        target=lambda: index_tasks.bulk_reindex_type_task.run("object", coalesce=True)
    )
    worker.start()
    assert started.wait(5)

    reindex_state.request_bulk_reindex("place")
    assert index_tasks.bulk_reindex_type_task.run("place", coalesce=True)["status"] == "deferred"
    release.set()
    worker.join(5)

    # The finished object run resubmitted the deferred place rebuild.
    assert enqueued[-1] == ("place", {"coalesce": True})
    assert index_tasks.bulk_reindex_type_task.run("place", coalesce=True)["status"] == "ok"
    assert runs == ["object", "place"]


def test_full_rebuild_request_coalesces_and_is_resubmitted(redis_server, enqueued) -> None:
    assert reindex_state.request_full_rebuild() is True
    assert reindex_state.request_full_rebuild() is False
    assert enqueued == [({"coalesce": True},)]
    _client(redis_server).delete(reindex_state.queued_key(reindex_state.FULL))
    assert reindex_state.resubmit_pending(["object"]) == [reindex_state.FULL]
