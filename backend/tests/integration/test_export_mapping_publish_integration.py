# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Integration test for export mapping set republish (Phase 6): publishing a
new draft while a previous revision is already published must archive the
old revision and publish the new one atomically, without violating the
partial unique index on (format_key, profile_id, record_type, target_subtype)
WHERE status='published'."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_republish_archives_previous_published_revision(
    async_client: AsyncClient, auth_headers: dict
) -> None:
    create_payload = {
        "format_key": "oai_dc",
        "profile_id": "oai_dc_simple",
        "record_type": "object",
        "name": "OAI-DC republish test",
    }
    r = await async_client.post("/v1/export-mapping-sets", headers=auth_headers, json=create_payload)
    assert r.status_code == 201
    first_set = r.json()

    r = await async_client.post(
        f"/v1/export-mapping-sets/{first_set['id']}/publish",
        headers={**auth_headers, "If-Match": str(first_set["version"])},
    )
    assert r.status_code == 200
    published_first = r.json()
    assert published_first["status"] == "published"

    # Second draft, based on the first published revision.
    r = await async_client.post(
        "/v1/export-mapping-sets",
        headers=auth_headers,
        json={**create_payload, "based_on_id": published_first["id"]},
    )
    assert r.status_code == 201
    second_set = r.json()

    r = await async_client.post(
        f"/v1/export-mapping-sets/{second_set['id']}/publish",
        headers={**auth_headers, "If-Match": str(second_set["version"])},
    )
    assert r.status_code == 200, r.text
    published_second = r.json()
    assert published_second["status"] == "published"

    r = await async_client.get(f"/v1/export-mapping-sets/{published_first['id']}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "archived"
