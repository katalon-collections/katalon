# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Issue #389: Working Sets must enforce the `working_sets` feature at the API
layer, and resolving/sharing a set must only surface records the *viewing*
user (not just the owner) may read.
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


async def _create_procedure(async_client, auth_headers, idno: str) -> str:
    res = await async_client.post(
        "/v1/procedures",
        headers=auth_headers,
        json={
            "idno": idno,
            "procedure_type": "conservation",
            "status": "draft",
            "metadata_": {"label": "Working-Set-Test-Vorgang"},
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


@pytest.mark.asyncio
async def test_working_sets_require_working_sets_feature(async_client, auth_headers) -> None:
    cataloger_headers = await _create_role_user(async_client, auth_headers, "cataloger")

    async with _feature_revoked(async_client, auth_headers, "cataloger", "working_sets"):
        res = await async_client.get("/v1/working-sets", headers=cataloger_headers)
        assert res.status_code == 403

        create_res = await async_client.post(
            "/v1/working-sets",
            headers=cataloger_headers,
            json={"name": "Denied", "record_type": "object", "is_shared": False},
        )
        assert create_res.status_code == 403


@pytest.mark.asyncio
async def test_shared_working_set_hides_records_recipient_cannot_read(async_client, auth_headers) -> None:
    proc_idno = f"PRO-WS-{uuid.uuid4().hex[:10]}"
    proc_id = await _create_procedure(async_client, auth_headers, proc_idno)

    create_res = await async_client.post(
        "/v1/working-sets",
        headers=auth_headers,
        json={"name": "Shared Procedures", "record_type": "procedure", "is_shared": True},
    )
    assert create_res.status_code == 201, create_res.text
    set_id = create_res.json()["id"]

    add_res = await async_client.post(
        f"/v1/working-sets/{set_id}/items",
        headers=auth_headers,
        json={"record_ids": [proc_id]},
    )
    assert add_res.status_code == 200, add_res.text

    # Owner (admin) sees the resolved item with its real label/idno.
    owner_detail = (
        await async_client.get(f"/v1/working-sets/{set_id}", headers=auth_headers)
    ).json()
    assert any(item["idno"] == proc_idno for item in owner_detail["items"])

    # A cataloger normally has procedure-read — strip it so this recipient
    # cannot read the shared set's contained record type.
    cataloger_headers = await _create_role_user(async_client, auth_headers, "cataloger")

    async with _record_permission_revoked(async_client, auth_headers, "cataloger", "procedure", "read"):
        recipient_detail_res = await async_client.get(
            f"/v1/working-sets/{set_id}", headers=cataloger_headers
        )
        assert recipient_detail_res.status_code == 200, recipient_detail_res.text
        recipient_detail = recipient_detail_res.json()
        assert all(item["record_id"] != proc_id for item in recipient_detail["items"])
        assert proc_idno not in recipient_detail_res.text
