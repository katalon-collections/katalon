# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Issue #388: storage location list/get must enforce record-read permission.

Before the fix, `list_storage_locations`/`get_storage_location` accepted any
authenticated (or even anonymous) caller regardless of role, even though the
permission matrix explicitly denies viewers read access to storage locations.
"""

import uuid

import pytest


async def _create_role_user(async_client, auth_headers: dict[str, str], role: str) -> dict[str, str]:
    email = f"{role}-{uuid.uuid4().hex[:10]}@katalon.dev"
    password = "Test1234"
    created = await async_client.post(
        "/v1/users", headers=auth_headers, json={"email": email, "password": password, "role": role},
    )
    assert created.status_code == 201, created.text
    token = (
        await async_client.post(
            "/v1/auth/token", data={"username": email, "password": password},
        )
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _create_storage_location(async_client, auth_headers: dict[str, str]) -> str:
    idno = f"LOC-{uuid.uuid4().hex[:10]}"
    create_res = await async_client.post(
        "/v1/storage-locations",
        headers=auth_headers,
        json={"idno": idno, "metadata_": {"label": "Test-Lagerort", "idno": idno}},
    )
    assert create_res.status_code == 201, create_res.text
    return create_res.json()["id"]


@pytest.mark.asyncio
async def test_viewer_cannot_list_or_get_storage_locations(async_client, auth_headers) -> None:
    loc_id = await _create_storage_location(async_client, auth_headers)
    viewer_headers = await _create_role_user(async_client, auth_headers, "viewer")

    list_res = await async_client.get("/v1/storage-locations", headers=viewer_headers)
    assert list_res.status_code == 403

    get_res = await async_client.get(f"/v1/storage-locations/{loc_id}", headers=viewer_headers)
    assert get_res.status_code == 403


@pytest.mark.asyncio
async def test_cataloger_retains_storage_location_read_access(async_client, auth_headers) -> None:
    loc_id = await _create_storage_location(async_client, auth_headers)
    cataloger_headers = await _create_role_user(async_client, auth_headers, "cataloger")

    list_res = await async_client.get("/v1/storage-locations", headers=cataloger_headers)
    assert list_res.status_code == 200
    assert any(item["id"] == loc_id for item in list_res.json()["items"])

    get_res = await async_client.get(f"/v1/storage-locations/{loc_id}", headers=cataloger_headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == loc_id


@pytest.mark.asyncio
async def test_storage_location_list_and_get_require_authentication(async_client, auth_headers) -> None:
    loc_id = await _create_storage_location(async_client, auth_headers)

    assert (await async_client.get("/v1/storage-locations")).status_code == 401
    assert (await async_client.get(f"/v1/storage-locations/{loc_id}")).status_code == 401


@pytest.mark.asyncio
async def test_viewer_cannot_list_objects_at_storage_location(async_client, auth_headers) -> None:
    loc_id = await _create_storage_location(async_client, auth_headers)
    viewer_headers = await _create_role_user(async_client, auth_headers, "viewer")

    res = await async_client.get(
        f"/v1/storage-locations/{loc_id}/objects", headers=viewer_headers
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_cataloger_can_list_objects_at_storage_location(async_client, auth_headers) -> None:
    loc_id = await _create_storage_location(async_client, auth_headers)
    cataloger_headers = await _create_role_user(async_client, auth_headers, "cataloger")

    res = await async_client.get(
        f"/v1/storage-locations/{loc_id}/objects", headers=cataloger_headers
    )
    assert res.status_code == 200
    assert res.json()["total"] == 0
