# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Regression tests for DB-only custom authority sources (adapters registered
purely via an `authority_sources` row with an `id` outside the builtin set).

`authority_service.list_sources()` only ever returns the hardcoded `_BUILTIN`
keys; the `/v1/authorities/` endpoints must not rely on it alone or custom
sources become invisible/unmanageable through the admin API.
"""
import uuid

import pytest
from httpx import AsyncClient


async def _insert_custom_source(is_enabled: bool = False) -> str:
    from katalon.core.models import AuthoritySource
    from katalon.database import AsyncSessionLocal

    source_id = f"custom-{uuid.uuid4().hex[:8]}"
    async with AsyncSessionLocal() as session:
        session.add(
            AuthoritySource(
                id=source_id,
                label="Custom Test Adapter",
                adapter_class="tests.fixtures.CustomAdapter",
                config={},
                is_enabled=is_enabled,
            )
        )
        await session.commit()
    return source_id


@pytest.mark.asyncio
async def test_list_sources_includes_db_only_custom_source(
    async_client: AsyncClient, auth_headers: dict
) -> None:
    source_id = await _insert_custom_source(is_enabled=True)

    r = await async_client.get("/v1/authorities/", headers=auth_headers)
    assert r.status_code == 200, r.text
    ids = {row["id"] for row in r.json()}
    assert source_id in ids
    entry = next(row for row in r.json() if row["id"] == source_id)
    assert entry["label"] == "Custom Test Adapter"
    assert entry["is_enabled"] is True


@pytest.mark.asyncio
async def test_update_source_toggles_db_only_custom_source(
    async_client: AsyncClient, auth_headers: dict
) -> None:
    source_id = await _insert_custom_source(is_enabled=True)

    r = await async_client.patch(
        f"/v1/authorities/{source_id}", headers=auth_headers, json={"is_enabled": False}
    )
    assert r.status_code == 200, r.text
    assert r.json()["is_enabled"] is False

    listed = await async_client.get("/v1/authorities/", headers=auth_headers)
    entry = next(row for row in listed.json() if row["id"] == source_id)
    assert entry["is_enabled"] is False


@pytest.mark.asyncio
async def test_update_source_rejects_truly_unknown_source(
    async_client: AsyncClient, auth_headers: dict
) -> None:
    r = await async_client.patch(
        "/v1/authorities/does-not-exist-anywhere",
        headers=auth_headers,
        json={"is_enabled": True},
    )
    assert r.status_code == 404
