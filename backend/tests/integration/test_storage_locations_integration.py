# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_storage_location_requires_idno(
    async_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    # No idno, no auto-numbering schema configured -> rejected.
    res = await async_client.post(
        "/v1/storage-locations",
        headers=auth_headers,
        json={"metadata_": {}},
    )
    assert res.status_code == 422
    assert "Pflichtfeld" in res.json()["detail"]


@pytest.mark.asyncio
async def test_storage_location_crud_has_no_status_field(
    async_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    idno = f"LOC-{uuid.uuid4().hex[:10]}"
    create_res = await async_client.post(
        "/v1/storage-locations",
        headers=auth_headers,
        json={"idno": idno, "metadata_": {"label": "Test-Lagerort"}},
    )
    assert create_res.status_code == 201
    data = create_res.json()
    assert data["idno"] == idno
    assert "status" not in data

    loc_id = data["id"]

    # Duplicate idno rejected.
    dup_res = await async_client.post(
        "/v1/storage-locations",
        headers=auth_headers,
        json={"idno": idno, "metadata_": {"label": "Anderer Lagerort"}},
    )
    assert dup_res.status_code == 400

    # Update clearing idno is rejected.
    clear_res = await async_client.put(
        f"/v1/storage-locations/{loc_id}",
        headers={**auth_headers, "If-Match": str(data["version"])},
        json={"idno": "", "metadata_": {"label": "Test-Lagerort"}},
    )
    assert clear_res.status_code == 422
    assert "Pflichtfeld" in clear_res.json()["detail"]

    # Update with a new idno succeeds.
    new_idno = f"LOC-{uuid.uuid4().hex[:10]}"
    update_res = await async_client.put(
        f"/v1/storage-locations/{loc_id}",
        headers={**auth_headers, "If-Match": str(data["version"])},
        json={"idno": new_idno, "metadata_": {"label": "Test-Lagerort"}},
    )
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["idno"] == new_idno
    assert "status" not in updated
