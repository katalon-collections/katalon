# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Full rebuild: fresh physical index, catch-up, atomic alias switch."""

import asyncio
import uuid

import pytest
from sqlalchemy import text


async def _create_object(async_client, auth_headers, label: str) -> str:
    response = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={"idno": f"FR-{uuid.uuid4().hex[:10]}", "status": "public", "metadata_": {"label": label}},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


@pytest.mark.asyncio
async def test_full_rebuild_replaces_legacy_index_and_catches_up(
    async_client, auth_headers, fake_es, fake_reindex_redis, migrated_database
) -> None:
    from katalon.integrations.elasticsearch import INDEX_NAME
    from katalon.workers import index_tasks

    first = await _create_object(async_client, auth_headers, "erste")
    changed = await _create_object(async_client, auth_headers, "wird geändert")
    # Stale doc and a doc with a "broken" shape in the legacy concrete index.
    fake_es.docs["stale"] = {"record_type": "object", "label": "weg"}
    fake_es.docs[first] = {"record_type": "object", "label": "alt"}

    async def edit_during_build() -> None:
        # A change committed while the build runs (after its id snapshot).
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(migrated_database)
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        "UPDATE objects SET metadata = jsonb_set(metadata, '{label}', "
                        "'\"geändert\"'), updated_at = now() at time zone 'utc' WHERE id = :id"
                    ),
                    {"id": uuid.UUID(changed)},
                )
        finally:
            await engine.dispose()

    fake_es.on_first_batch = edit_during_build

    report = await asyncio.to_thread(index_tasks.reindex_all_task.run)

    assert report["status"] == "ok"
    new_index = report["index"]
    assert new_index.startswith(f"{INDEX_NAME}_")
    assert report["replaced"] == [INDEX_NAME]
    assert fake_es.alias_target == new_index
    assert set(fake_es.indices_data) == {new_index}
    assert "stale" not in fake_es.docs
    assert first in fake_es.docs
    assert report["types"]["object"]["caught_up"] >= 1
    assert "geändert" in str(fake_es.docs[changed])


@pytest.mark.asyncio
async def test_failed_full_rebuild_keeps_live_index(
    async_client, auth_headers, fake_es, fake_reindex_redis, monkeypatch
) -> None:
    from katalon.workers import index_tasks

    await _create_object(async_client, auth_headers, "bleibt")
    fake_es.docs["live"] = {"record_type": "object"}

    async def broken_hook() -> None:
        raise RuntimeError("es node lost")

    fake_es.on_first_batch = broken_hook
    with pytest.raises(RuntimeError):
        await asyncio.to_thread(index_tasks.reindex_all_task.run)

    assert fake_es.alias_target is None  # still the legacy concrete index
    assert "live" in fake_es.docs
    assert len(fake_es.indices_data) == 1  # half-built index removed


@pytest.mark.asyncio
async def test_old_index_cleanup_failure_keeps_new_live_index(
    async_client, auth_headers, fake_es, fake_reindex_redis, monkeypatch
) -> None:
    from katalon.workers import index_tasks

    object_id = await _create_object(async_client, auth_headers, "survives cleanup")
    old = fake_es.name
    fake_es.alias_target = old
    original_delete = fake_es.indices.delete

    async def fail_old_delete(index: str) -> None:
        if index == old:
            raise RuntimeError("old-index cleanup failed")
        await original_delete(index)

    monkeypatch.setattr(fake_es.indices, "delete", fail_old_delete)
    report = await asyncio.to_thread(index_tasks.reindex_all_task.run)

    assert report["status"] == "ok"
    assert fake_es.alias_target == report["index"]
    assert object_id in fake_es.docs
    assert old in fake_es.indices_data


@pytest.mark.asyncio
async def test_switch_timeout_does_not_delete_a_possibly_live_index(
    async_client, auth_headers, fake_es, fake_reindex_redis, monkeypatch
) -> None:
    from katalon.workers import index_tasks

    object_id = await _create_object(async_client, auth_headers, "survives timeout")
    fake_es.alias_target = fake_es.name
    original_update = fake_es.indices.update_aliases

    async def switch_then_timeout(body: dict) -> None:
        await original_update(body)
        raise TimeoutError("response lost after ES switched")

    monkeypatch.setattr(fake_es.indices, "update_aliases", switch_then_timeout)
    with pytest.raises(TimeoutError):
        await asyncio.to_thread(index_tasks.reindex_all_task.run)

    assert fake_es.alias_target != fake_es.name
    assert object_id in fake_es.docs
