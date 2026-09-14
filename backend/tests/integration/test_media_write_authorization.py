# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Issue #389: media write operations (upload/patch/delete) must require the
`media` feature *and* write permission on the associated object — replacing
the previous coarse `manage_content` gate.
"""

import uuid
from contextlib import asynccontextmanager

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


@asynccontextmanager
async def _feature_revoked(async_client, auth_headers, role: str, feature: str):
    """Temporarily drop `feature` from `role`'s feature permissions, restoring
    the role's exact prior set afterward — role permissions are global state
    shared by every user of that role across the whole test session."""
    current = (await async_client.get("/v1/users/features", headers=auth_headers)).json()
    role_rows = [row for row in current if row["role"] == role]
    remaining = [row for row in role_rows if row["feature"] != feature]
    res = await async_client.put(
        f"/v1/users/features/{role}", headers=auth_headers, json={"features": remaining},
    )
    assert res.status_code == 200, res.text
    try:
        yield
    finally:
        restore = await async_client.put(
            f"/v1/users/features/{role}", headers=auth_headers, json={"features": role_rows},
        )
        assert restore.status_code == 200, restore.text


@asynccontextmanager
async def _record_permission_revoked(async_client, auth_headers, role: str, record_type: str, action: str):
    """Temporarily drop one (record_type, action) grant from `role`, restoring
    the role's exact prior set afterward (see `_feature_revoked`)."""
    current = (await async_client.get("/v1/users/permissions", headers=auth_headers)).json()
    role_rows = [row for row in current if row["role"] == role]
    remaining = [
        row for row in role_rows
        if not (row["record_type"] == record_type and row["action"] == action)
    ]
    res = await async_client.put(
        f"/v1/users/permissions/{role}", headers=auth_headers, json={"permissions": remaining},
    )
    assert res.status_code == 200, res.text
    try:
        yield
    finally:
        restore = await async_client.put(
            f"/v1/users/permissions/{role}", headers=auth_headers, json={"permissions": role_rows},
        )
        assert restore.status_code == 200, restore.text


async def _create_object(async_client, auth_headers) -> str:
    idno = f"OBJ-MEDIA-{uuid.uuid4().hex[:10]}"
    res = await async_client.post(
        "/v1/objects", headers=auth_headers, json={"idno": idno, "status": "draft", "metadata_": {}},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


_PDF_BYTES = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


@pytest.mark.asyncio
async def test_media_upload_requires_media_feature(async_client, auth_headers) -> None:
    object_id = await _create_object(async_client, auth_headers)
    cataloger_headers = await _create_role_user(async_client, auth_headers, "cataloger")

    async with _feature_revoked(async_client, auth_headers, "cataloger", "media"):
        res = await async_client.post(
            f"/v1/objects/{object_id}/media",
            headers=cataloger_headers,
            files={"file": ("doc.pdf", _PDF_BYTES, "application/pdf")},
        )
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_media_upload_requires_object_update_permission(async_client, auth_headers) -> None:
    object_id = await _create_object(async_client, auth_headers)
    cataloger_headers = await _create_role_user(async_client, auth_headers, "cataloger")

    async with _record_permission_revoked(async_client, auth_headers, "cataloger", "object", "update"):
        res = await async_client.post(
            f"/v1/objects/{object_id}/media",
            headers=cataloger_headers,
            files={"file": ("doc.pdf", _PDF_BYTES, "application/pdf")},
        )
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_media_upload_patch_delete_succeed_for_authorized_cataloger(async_client, auth_headers) -> None:
    object_id = await _create_object(async_client, auth_headers)
    cataloger_headers = await _create_role_user(async_client, auth_headers, "cataloger")

    upload_res = await async_client.post(
        f"/v1/objects/{object_id}/media",
        headers=cataloger_headers,
        files={"file": ("doc.pdf", _PDF_BYTES, "application/pdf")},
    )
    assert upload_res.status_code == 201, upload_res.text
    media_id = upload_res.json()["id"]

    patch_res = await async_client.patch(
        f"/v1/objects/{object_id}/media/{media_id}",
        headers=cataloger_headers,
        json={"is_public": False},
    )
    assert patch_res.status_code == 200, patch_res.text

    delete_res = await async_client.delete(
        f"/v1/objects/{object_id}/media/{media_id}", headers=cataloger_headers
    )
    assert delete_res.status_code == 204, delete_res.text


@pytest.mark.asyncio
async def test_media_patch_and_delete_require_media_feature(async_client, auth_headers) -> None:
    object_id = await _create_object(async_client, auth_headers)
    upload_res = await async_client.post(
        f"/v1/objects/{object_id}/media",
        headers=auth_headers,
        files={"file": ("doc.pdf", _PDF_BYTES, "application/pdf")},
    )
    assert upload_res.status_code == 201, upload_res.text
    media_id = upload_res.json()["id"]

    cataloger_headers = await _create_role_user(async_client, auth_headers, "cataloger")

    async with _feature_revoked(async_client, auth_headers, "cataloger", "media"):
        patch_res = await async_client.patch(
            f"/v1/objects/{object_id}/media/{media_id}",
            headers=cataloger_headers,
            json={"is_public": False},
        )
        assert patch_res.status_code == 403

        delete_res = await async_client.delete(
            f"/v1/objects/{object_id}/media/{media_id}", headers=cataloger_headers
        )
        assert delete_res.status_code == 403
