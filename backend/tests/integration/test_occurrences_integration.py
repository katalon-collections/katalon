# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import asyncio
import uuid

import pytest


@pytest.mark.asyncio
async def test_occurrence_crud_roundtrip(async_client, auth_headers) -> None:
    idno = f"INT-OCC-{uuid.uuid4().hex[:12]}"

    create_response = await async_client.post(
        "/v1/occurrences",
        headers=auth_headers,
        json={
            "idno": idno,
            "status": "draft",
            "metadata_": {"label": "Integration occurrence"},
        },
    )
    assert create_response.status_code == 201

    created = create_response.json()
    occ_id = created["id"]
    assert created["idno"] == idno
    assert created["status"] == "draft"

    get_response = await async_client.get(f"/v1/occurrences/{occ_id}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["metadata_"]["label"] == "Integration occurrence"

    update_response = await async_client.put(
        f"/v1/occurrences/{occ_id}",
        headers=auth_headers,
        json={
            "idno": idno,
            "status": "public",
            "metadata_": {"label": "Updated integration occurrence"},
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "public"

    delete_response = await async_client.delete(f"/v1/occurrences/{occ_id}", headers=auth_headers)
    assert delete_response.status_code == 204

    missing_response = await async_client.get(f"/v1/occurrences/{occ_id}", headers=auth_headers)
    assert missing_response.status_code == 404


@pytest.mark.asyncio
async def test_occurrence_publish_requires_valid_metadata(async_client, auth_headers) -> None:
    idno = f"PUB-OCC-{uuid.uuid4().hex[:12]}"
    create_response = await async_client.post(
        "/v1/occurrences",
        headers=auth_headers,
        json={
            "idno": idno,
            "status": "draft",
            "metadata_": {},
        },
    )
    assert create_response.status_code == 201
    occ_id = create_response.json()["id"]

    publish_response = await async_client.post(
        f"/v1/occurrences/{occ_id}/publish", headers=auth_headers
    )
    assert publish_response.status_code in (200, 422)

    delete_response = await async_client.delete(f"/v1/occurrences/{occ_id}", headers=auth_headers)
    assert delete_response.status_code == 204


@pytest.mark.asyncio
async def test_concurrent_duplicate_occurrence_idno_returns_client_error(
    async_client, auth_headers
) -> None:
    idno = f"DUP-OCC-{uuid.uuid4().hex[:12]}"
    payload = {
        "idno": idno,
        "status": "draft",
        "metadata_": {},
    }
    responses = await asyncio.gather(
        async_client.post("/v1/occurrences", headers=auth_headers, json=payload),
        async_client.post("/v1/occurrences", headers=auth_headers, json=payload),
    )
    assert sorted(response.status_code for response in responses) == [201, 400]
