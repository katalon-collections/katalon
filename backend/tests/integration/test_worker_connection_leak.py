# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""A failing reindex build must not leave worker connections open on the DB server."""

import asyncio
import uuid

import pytest
from sqlalchemy import text


async def _create_object(async_client, auth_headers) -> None:
    response = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={"idno": f"LEAK-{uuid.uuid4().hex[:12]}", "status": "draft", "metadata_": {}},
    )
    assert response.status_code == 201, response.text


async def _worker_connections(migrated_database: str) -> int:
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(migrated_database)
    try:
        async with engine.connect() as conn:
            return int(
                await conn.scalar(
                    text(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE application_name = 'katalon-worker' AND pid <> pg_backend_pid()"
                    )
                )
            )
    finally:
        await engine.dispose()


class _Progress:
    def update(self, **_kwargs) -> None:
        return None


@pytest.mark.asyncio
async def test_failing_reindex_build_leaves_no_worker_connections(
    async_client, auth_headers, monkeypatch, migrated_database, fake_es
) -> None:
    import katalon.services.search_service as search_service
    from katalon.workers import index_tasks

    for _ in range(12):
        await _create_object(async_client, auth_headers)
    monkeypatch.setattr(index_tasks, "REINDEX_BUILD_CONCURRENCY", 6)

    started = 0

    async def failing_build(_record_type, _record, session):
        nonlocal started
        started += 1
        position = started
        # Keep sibling builds mid-query when one of them fails.
        await session.execute(text("SELECT pg_sleep(0.2)"))
        if position == 3:
            raise RuntimeError("build failed")
        return {}

    monkeypatch.setattr(search_service, "build_index_doc", failing_build)

    with pytest.raises(RuntimeError, match="build failed"):
        await asyncio.to_thread(
            asyncio.run,
            index_tasks._stream_reindex("object", _Progress(), index=fake_es.name),
        )

    assert await _worker_connections(migrated_database) == 0
