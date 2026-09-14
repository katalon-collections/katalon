# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Issue #388: snapshot listing must require record-read permission.

Before the fix, `GET /v1/{type}/{id}/snapshots` took no user dependency at
all — a fully anonymous, unauthenticated request received the complete
snapshot payload (full historical metadata). Procedure and storage_location
have no snapshot feature at all and are excluded from this parametrization;
the other five core record types (object, entity, place, occurrence,
collection) all expose `.../snapshots` and are covered explicitly.
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


@pytest.mark.parametrize("route", ["objects", "entities", "places", "occurrences", "collections"])
@pytest.mark.asyncio
async def test_snapshot_list_requires_authentication(async_client, auth_headers, route: str) -> None:
    payload = {"idno": f"SNAP-{uuid.uuid4().hex[:12]}", "status": "draft", "metadata_": {}}
    created = await async_client.post(f"/v1/{route}", headers=auth_headers, json=payload)
    assert created.status_code == 201, created.text
    record_id = created.json()["id"]

    snapshot = await async_client.post(
        f"/v1/{route}/{record_id}/snapshots", headers=auth_headers, json={"label": "before change"},
    )
    assert snapshot.status_code == 201, snapshot.text

    anonymous = await async_client.get(f"/v1/{route}/{record_id}/snapshots")
    assert anonymous.status_code == 401


@pytest.mark.parametrize("route", ["objects", "entities", "places", "occurrences", "collections"])
@pytest.mark.asyncio
async def test_snapshot_list_succeeds_for_authenticated_reader(
    async_client, auth_headers, route: str
) -> None:
    payload = {"idno": f"SNAP-{uuid.uuid4().hex[:12]}", "status": "draft", "metadata_": {}}
    created = await async_client.post(f"/v1/{route}", headers=auth_headers, json=payload)
    assert created.status_code == 201, created.text
    record_id = created.json()["id"]

    snapshot = await async_client.post(
        f"/v1/{route}/{record_id}/snapshots", headers=auth_headers, json={"label": "before change"},
    )
    assert snapshot.status_code == 201, snapshot.text

    # A non-admin role that the permission matrix grants read access to
    # (viewer reads all five of these types by default) must still succeed —
    # the fix must not regress legitimate read access.
    viewer_headers = await _create_role_user(async_client, auth_headers, "viewer")
    listed = await async_client.get(f"/v1/{route}/{record_id}/snapshots", headers=viewer_headers)
    assert listed.status_code == 200
    assert any(s["id"] == snapshot.json()["id"] for s in listed.json())
