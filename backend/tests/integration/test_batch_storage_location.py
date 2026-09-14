# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid

import pytest


@pytest.fixture
def unique_suffix():
    return uuid.uuid4().hex[:12]


async def _create_storage_location(
    async_client, auth_headers, idno: str, metadata: dict | None = None, subtype: str | None = None
):
    meta = {"label": f"Location {idno}"}
    if metadata:
        meta.update(metadata)
    payload = {
        "idno": idno,
        "metadata_": meta,
    }
    if subtype:
        payload["storage_location_type"] = subtype
    response = await async_client.post(
        "/v1/storage-locations",
        headers=auth_headers,
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_field_definition(
    async_client,
    auth_headers,
    target_type: str,
    name: str,
    field_type: str = "text",
    is_repeatable: bool = False,
):
    response = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": target_type,
            "name": name,
            "label": {"de": name, "en": name},
            "field_type": field_type,
            "is_repeatable": is_repeatable,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_batch_storage_location_set_field(async_client, auth_headers, unique_suffix):
    field_name = f"notes_{unique_suffix}"
    await _create_field_definition(
        async_client,
        auth_headers,
        target_type="storage_location",
        name=field_name,
        field_type="text",
    )

    loc1 = await _create_storage_location(
        async_client, auth_headers, f"LOC-BATCH-1-{unique_suffix}", metadata={field_name: "Initial 1"}
    )
    loc2 = await _create_storage_location(
        async_client, auth_headers, f"LOC-BATCH-2-{unique_suffix}", metadata={field_name: "Initial 2"}
    )

    response = await async_client.post(
        "/v1/batch/storage_location",
        headers=auth_headers,
        json={
            "ids": [loc1["id"], loc2["id"]],
            "operation": {"type": "set_field", "field": field_name, "value": "Regal 4 - Fach B"},
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["affected"] == 2
    assert result["errors"] == []
    assert result["batch_job_id"] is not None

    for loc_id in (loc1["id"], loc2["id"]):
        updated = (await async_client.get(f"/v1/storage-locations/{loc_id}", headers=auth_headers)).json()
        assert updated["metadata_"][field_name] == "Regal 4 - Fach B"

        audit_res = await async_client.get(
            f"/v1/audit?record_type=storage_location&record_id={loc_id}", headers=auth_headers
        )
        assert audit_res.status_code == 200
        audit_entries = audit_res.json()
        assert any(entry["action"] == "batch_update" for entry in audit_entries)
        assert any(
            entry.get("changed_fields", {}).get("batch_job_id") == result["batch_job_id"]
            for entry in audit_entries
        )


@pytest.mark.asyncio
async def test_batch_storage_location_set_status_fails(async_client, auth_headers, unique_suffix):
    loc = await _create_storage_location(
        async_client, auth_headers, f"LOC-STATUS-{unique_suffix}"
    )

    response = await async_client.post(
        "/v1/batch/storage_location",
        headers=auth_headers,
        json={
            "ids": [loc["id"]],
            "operation": {"type": "set_status", "value": "public"},
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["affected"] == 0
    assert len(result["errors"]) == 1
    assert "Ungültiger Status 'public' für storage_location" in result["errors"][0]

    # Verify that storage_location still exists and unchanged
    fetched = (await async_client.get(f"/v1/storage-locations/{loc['id']}", headers=auth_headers)).json()
    assert "status" not in fetched
