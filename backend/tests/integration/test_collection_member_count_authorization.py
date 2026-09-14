# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Issue #385, point 1: `member_objects_count` on the portal collection detail
must be filtered to `object` records the *object*-read-permission of the
viewer allows, not just their `collection`-read permission. A staff role with
`collection:read` but not `object:read` must never see non-public objects
counted in."""

import uuid

import pytest


async def _create_viewer_without_object_read(
    async_client, auth_headers
) -> tuple[dict[str, str], list[dict[str, str]]]:
    """Returns auth headers for a fresh viewer plus the role's original
    permission set, so the caller can restore it — `role_permissions` is
    global, shared-session state across the whole integration test run, not
    scoped to this test or user."""
    email = f"viewer-{uuid.uuid4().hex[:10]}@katalon.dev"
    password = "Test1234"
    created = await async_client.post(
        "/v1/users",
        headers=auth_headers,
        json={"email": email, "password": password, "role": "viewer"},
    )
    assert created.status_code == 201, created.text

    perms_res = await async_client.get("/v1/users/permissions", headers=auth_headers)
    assert perms_res.status_code == 200, perms_res.text
    original_viewer_perms = [
        {"role": "viewer", "record_type": p["record_type"], "action": p["action"]}
        for p in perms_res.json()
        if p["role"] == "viewer"
    ]
    viewer_perms = [
        p for p in original_viewer_perms if not (p["record_type"] == "object" and p["action"] == "read")
    ]
    replace_res = await async_client.put(
        "/v1/users/permissions/viewer",
        headers=auth_headers,
        json={"permissions": viewer_perms},
    )
    assert replace_res.status_code == 200, replace_res.text
    assert not any(p["record_type"] == "object" for p in replace_res.json())

    token = (
        await async_client.post(
            "/v1/auth/token", data={"username": email, "password": password}
        )
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, original_viewer_perms


async def _create_collection_with_public_and_internal_member(async_client, auth_headers) -> str:
    col_res = await async_client.post(
        "/v1/collections",
        headers=auth_headers,
        json={
            "idno": f"COL-{uuid.uuid4().hex[:10]}",
            "status": "public",
            "metadata_": {"label": "Test-Sammlung"},
        },
    )
    assert col_res.status_code == 201, col_res.text
    col_id = col_res.json()["id"]

    public_obj = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"OBJ-{uuid.uuid4().hex[:10]}",
            "status": "public",
            "metadata_": {"label": "Öffentliches Objekt"},
        },
    )
    assert public_obj.status_code == 201, public_obj.text

    internal_obj = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"OBJ-{uuid.uuid4().hex[:10]}",
            "status": "internal",
            "metadata_": {"label": "Internes Objekt"},
        },
    )
    assert internal_obj.status_code == 201, internal_obj.text

    for obj in (public_obj, internal_obj):
        rel_res = await async_client.post(
            "/v1/relations",
            headers=auth_headers,
            json={
                "from_type": "object",
                "from_id": obj.json()["id"],
                "to_type": "collection",
                "to_id": col_id,
                "relation_type": "member_of",
            },
        )
        assert rel_res.status_code == 201, rel_res.text

    return col_id


@pytest.mark.asyncio
async def test_viewer_without_object_read_sees_only_public_member_count(
    async_client, auth_headers
) -> None:
    col_id = await _create_collection_with_public_and_internal_member(async_client, auth_headers)
    viewer_headers, original_viewer_perms = await _create_viewer_without_object_read(
        async_client, auth_headers
    )
    try:
        res = await async_client.get(f"/portal/v1/collections/{col_id}", headers=viewer_headers)
        assert res.status_code == 200, res.text
        assert res.json()["member_objects_count"] == 1
    finally:
        restore = await async_client.put(
            "/v1/users/permissions/viewer",
            headers=auth_headers,
            json={"permissions": original_viewer_perms},
        )
        assert restore.status_code == 200, restore.text


@pytest.mark.asyncio
async def test_cataloger_with_object_read_sees_full_member_count(
    async_client, auth_headers
) -> None:
    col_id = await _create_collection_with_public_and_internal_member(async_client, auth_headers)

    email = f"cataloger-{uuid.uuid4().hex[:10]}@katalon.dev"
    password = "Test1234"
    created = await async_client.post(
        "/v1/users",
        headers=auth_headers,
        json={"email": email, "password": password, "role": "cataloger"},
    )
    assert created.status_code == 201, created.text
    token = (
        await async_client.post(
            "/v1/auth/token", data={"username": email, "password": password}
        )
    ).json()["access_token"]
    cataloger_headers = {"Authorization": f"Bearer {token}"}

    res = await async_client.get(f"/portal/v1/collections/{col_id}", headers=cataloger_headers)
    assert res.status_code == 200, res.text
    assert res.json()["member_objects_count"] == 2
