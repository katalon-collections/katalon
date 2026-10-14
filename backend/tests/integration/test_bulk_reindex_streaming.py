# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Streaming bulk reindex against a real DB with an in-memory ES double."""

import asyncio
import uuid

import pytest
from sqlalchemy import text


async def _create_object(async_client, auth_headers, label: str) -> str:
    response = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"STREAM-{uuid.uuid4().hex[:12]}",
            "status": "draft",
            "metadata_": {"label": label},
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


@pytest.mark.asyncio
async def test_streaming_reindex_batches_and_removes_only_stale_docs(
    async_client, auth_headers, monkeypatch, migrated_database, fake_es, fake_reindex_redis
) -> None:
    from katalon.workers import index_tasks

    ids = [await _create_object(async_client, auth_headers, f"stream {i}") for i in range(5)]
    deleted_id = await _create_object(async_client, auth_headers, "gone")
    assert (
        await async_client.delete(f"/v1/objects/{deleted_id}", headers=auth_headers)
    ).status_code == 204

    es = fake_es
    monkeypatch.setattr(index_tasks, "REINDEX_BATCH_SIZE", 2)
    monkeypatch.setattr(index_tasks, "REINDEX_BUILD_CONCURRENCY", 3)

    orphan_id = str(uuid.uuid4())
    es.docs[orphan_id] = {"record_type": "object", "label": "orphan"}
    es.docs[deleted_id] = {"record_type": "object", "label": "gone"}
    es.docs[ids[0]] = {"record_type": "object", "label": "outdated"}
    other_type_id = str(uuid.uuid4())
    es.docs[other_type_id] = {"record_type": "place", "label": "untouched"}

    # A record created (and indexed on its own) after the run took its id
    # snapshot must survive the stale sweep.
    late_id = str(uuid.uuid4())

    async def create_late_record() -> None:
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(migrated_database)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        "CREATE TEMP TABLE late_obj AS SELECT * FROM objects WHERE id = :src;"
                    ),
                    {"src": uuid.UUID(ids[1])},
                )
                await conn.execute(
                    text("UPDATE late_obj SET id = :new, idno = :idno"),
                    {"new": uuid.UUID(late_id), "idno": f"LATE-{late_id[:8]}"},
                )
                await conn.execute(text("INSERT INTO objects SELECT * FROM late_obj"))
        finally:
            await engine.dispose()
        es.docs[late_id] = {"record_type": "object", "label": "late"}

    es.on_first_batch = create_late_record

    report = await asyncio.to_thread(index_tasks.bulk_reindex_type_task.run, "object")

    assert report["status"] == "ok"
    assert max(es.batch_sizes) <= 2
    for record_id in ids:
        assert record_id in es.docs
    assert es.docs[ids[0]].get("label") != "outdated"
    assert deleted_id not in es.docs
    assert orphan_id not in es.docs
    assert late_id in es.docs
    assert other_type_id in es.docs
    assert report["removed"] == 2
