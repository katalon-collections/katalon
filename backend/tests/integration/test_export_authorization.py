# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Issue #389: bulk export must require the `export` feature and must not
leak records the caller has no record-read permission for (or their status,
idno, or count) through the CSV/JSON dump.
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


async def _create_procedure(async_client, auth_headers, idno: str) -> str:
    res = await async_client.post(
        "/v1/procedures",
        headers=auth_headers,
        json={
            "idno": idno,
            "procedure_type": "conservation",
            "status": "draft",
            "metadata_": {"label": "Export-Test-Vorgang"},
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


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


@pytest.mark.asyncio
async def test_export_requires_export_feature(async_client, auth_headers) -> None:
    cataloger_headers = await _create_role_user(async_client, auth_headers, "cataloger")

    async with _feature_revoked(async_client, auth_headers, "cataloger", "export"):
        res = await async_client.get(
            "/v1/export/object", headers=cataloger_headers, params={"format": "csv"}
        )
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_export_csv_excludes_records_unreadable_by_caller(async_client, auth_headers) -> None:
    # Viewer keeps the `export` feature by default but is hard-denied
    # record-read on `procedure` (has_record_permission special-cases it) —
    # every procedure export row must therefore be dropped for a viewer,
    # never surfaced via idno/label/status/count.
    idno = f"PRO-EXPORT-{uuid.uuid4().hex[:10]}"
    await _create_procedure(async_client, auth_headers, idno)
    viewer_headers = await _create_role_user(async_client, auth_headers, "viewer")

    res = await async_client.get(
        "/v1/export/procedure", headers=viewer_headers, params={"format": "csv"}
    )
    assert res.status_code == 200
    assert idno not in res.text

    # The privileged creator (admin) still sees it — confirms this is a
    # visibility filter, not a blanket break of procedure export.
    admin_res = await async_client.get(
        "/v1/export/procedure", headers=auth_headers, params={"format": "csv"}
    )
    assert admin_res.status_code == 200
    assert idno in admin_res.text


@pytest.mark.asyncio
async def test_export_json_excludes_records_unreadable_by_caller(async_client, auth_headers) -> None:
    idno = f"PRO-EXPORT-JSON-{uuid.uuid4().hex[:10]}"
    await _create_procedure(async_client, auth_headers, idno)
    viewer_headers = await _create_role_user(async_client, auth_headers, "viewer")

    res = await async_client.get(
        "/v1/export/procedure", headers=viewer_headers, params={"format": "json"}
    )
    assert res.status_code == 200
    body = res.json()
    assert all(row.get("idno") != idno for row in body)

    admin_res = await async_client.get(
        "/v1/export/procedure", headers=auth_headers, params={"format": "json"}
    )
    assert admin_res.status_code == 200
    assert idno in admin_res.text


@pytest.mark.asyncio
async def test_export_draft_object_hidden_when_read_permission_revoked(async_client, auth_headers) -> None:
    """Even for a type a role can normally read (object), revoking that
    role's read permission must fall back to public/published-only export —
    draft records disappear from the dump entirely."""
    draft_idno = f"OBJ-DRAFT-{uuid.uuid4().hex[:10]}"
    public_idno = f"OBJ-PUBLIC-{uuid.uuid4().hex[:10]}"
    await async_client.post(
        "/v1/objects", headers=auth_headers,
        json={"idno": draft_idno, "status": "draft", "metadata_": {}},
    )
    published = await async_client.post(
        "/v1/objects", headers=auth_headers,
        json={"idno": public_idno, "status": "public", "metadata_": {"label": "Public Export Test"}},
    )
    assert published.status_code == 201, published.text

    cataloger_headers = await _create_role_user(async_client, auth_headers, "cataloger")

    async with _record_permission_revoked(async_client, auth_headers, "cataloger", "object", "read"):
        res = await async_client.get(
            "/v1/export/object", headers=cataloger_headers, params={"format": "csv"}
        )
        assert res.status_code == 200
        assert draft_idno not in res.text
        assert public_idno in res.text
