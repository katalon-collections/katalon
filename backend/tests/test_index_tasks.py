# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import asyncio
import threading

from katalon.workers import index_tasks


class _Session:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def execute(self, _query):
        class _Scalars:
            @staticmethod
            def all():
                return []

        class _Result:
            @staticmethod
            def scalars():
                return _Scalars()

        return _Result()


class _Engine:
    async def dispose(self):
        return None


class _Redis:
    def __init__(self):
        self._lock = threading.Lock()

    def lock(self, _name, **_kwargs):
        return self._lock

    def close(self):
        return None


def test_bulk_reindex_serializes_same_record_type(monkeypatch) -> None:
    redis = _Redis()
    active = 0
    max_active = 0
    state_lock = threading.Lock()

    async def fake_reindex_type(_record_type, _records):
        nonlocal active, max_active
        with state_lock:
            active += 1
            max_active = max(max_active, active)
        await asyncio.sleep(0.05)
        with state_lock:
            active -= 1
        return 0

    monkeypatch.setattr(index_tasks, "_make_session", lambda: (lambda: _Session(), _Engine()))
    monkeypatch.setattr("redis.from_url", lambda *_args, **_kwargs: redis)
    monkeypatch.setattr("katalon.integrations.elasticsearch.reindex_type", fake_reindex_type)

    async def run_concurrently():
        return await asyncio.gather(
            asyncio.to_thread(index_tasks.bulk_reindex_type_task.run, "object"),
            asyncio.to_thread(index_tasks.bulk_reindex_type_task.run, "object"),
        )

    reports = asyncio.run(run_concurrently())

    assert [report["status"] for report in reports] == ["ok", "ok"]
    assert max_active == 1


def test_reindex_all_task_aggregates_errors_and_processes_all_types(monkeypatch) -> None:
    types_attempted: list[str] = []

    def fake_bulk(target_type: str):
        types_attempted.append(target_type)
        if target_type == "place":
            raise RuntimeError("Place reindex failed")
        return {"status": "ok", "indexed": 0, "target_type": target_type}

    monkeypatch.setattr(index_tasks, "bulk_reindex_type_task", fake_bulk)

    import pytest

    with pytest.raises(
        RuntimeError, match="reindex_all_task completed with errors: place: Place reindex failed"
    ):
        index_tasks.reindex_all_task.run()

    # Ensure all 7 types were still attempted despite "place" failing
    assert "object" in types_attempted
    assert "place" in types_attempted
    assert "storage_location" in types_attempted
    assert len(types_attempted) == 7
