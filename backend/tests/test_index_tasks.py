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
