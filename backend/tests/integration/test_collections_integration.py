# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_collection_crud_and_hierarchy(
    async_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    # 1. Create parent collection
    parent_res = await async_client.post(
        "/v1/collections",
        headers=auth_headers,
        json={
            "idno": f"COL-{uuid.uuid4().hex[:10]}",
            "status": "draft",
            "metadata_": {"label": "Parent Collection"},
        },
    )
    assert parent_res.status_code == 201
    parent_data = parent_res.json()
    parent_id = parent_data["id"]
    assert parent_data["parent_id"] is None

    # 2. Create child collection
    child_res = await async_client.post(
        "/v1/collections",
        headers=auth_headers,
        json={
            "idno": f"COL-{uuid.uuid4().hex[:10]}",
            "status": "draft",
            "parent_id": parent_id,
            "metadata_": {"label": "Child Collection"},
        },
    )
    assert child_res.status_code == 201
    child_data = child_res.json()
    child_id = child_data["id"]
    assert child_data["parent_id"] == parent_id

    # 3. Prevent self as parent
    self_parent_res = await async_client.put(
        f"/v1/collections/{parent_id}",
        headers={**auth_headers, "If-Match": str(parent_data["version"])},
        json={
            "idno": parent_data["idno"],
            "status": "draft",
            "parent_id": parent_id,
            "metadata_": {"label": "Parent Collection Updated"},
        },
    )
    assert self_parent_res.status_code == 422
    assert "eigene übergeordnete Sammlung" in self_parent_res.json()["detail"]

    # 4. Prevent cycle (parent cannot set its child as parent)
    cycle_res = await async_client.put(
        f"/v1/collections/{parent_id}",
        headers={**auth_headers, "If-Match": str(parent_data["version"])},
        json={
            "idno": parent_data["idno"],
            "status": "draft",
            "parent_id": child_id,
            "metadata_": {"label": "Parent Collection Updated"},
        },
    )
    assert cycle_res.status_code == 422
    assert "Zyklische Sammlungshierarchie" in cycle_res.json()["detail"]

    # 5. List with parent_id filter
    list_res = await async_client.get(
        f"/v1/collections?parent_id={parent_id}",
        headers=auth_headers,
    )
    assert list_res.status_code == 200
    items = list_res.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == child_id


@pytest.mark.asyncio
async def test_collection_snapshots_and_restore(
    async_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    create_res = await async_client.post(
        "/v1/collections",
        headers=auth_headers,
        json={
            "idno": f"COL-{uuid.uuid4().hex[:10]}",
            "status": "draft",
            "metadata_": {"label": "Original Title"},
        },
    )
    assert create_res.status_code == 201
    col_id = create_res.json()["id"]
    version = create_res.json()["version"]

    # Create snapshot
    snap_res = await async_client.post(
        f"/v1/collections/{col_id}/snapshots",
        headers=auth_headers,
        json={"label": "Initial version"},
    )
    assert snap_res.status_code == 201
    snap_id = snap_res.json()["id"]

    # Update collection
    update_res = await async_client.put(
        f"/v1/collections/{col_id}",
        headers={**auth_headers, "If-Match": str(version)},
        json={
            "idno": create_res.json()["idno"],
            "status": "internal",
            "metadata_": {"label": "Updated Title"},
        },
    )
    assert update_res.status_code == 200
    assert update_res.json()["metadata_"]["label"] == "Updated Title"
    new_version = update_res.json()["version"]

    # Restore snapshot
    restore_res = await async_client.post(
        f"/v1/collections/{col_id}/snapshots/{snap_id}/restore",
        headers={**auth_headers, "If-Match": str(new_version)},
    )
    assert restore_res.status_code == 200
    assert restore_res.json()["metadata_"]["label"] == "Original Title"


@pytest.mark.asyncio
async def test_collection_trash_and_restore(
    async_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    create_res = await async_client.post(
        "/v1/collections",
        headers=auth_headers,
        json={
            "idno": f"COL-{uuid.uuid4().hex[:10]}",
            "status": "draft",
            "metadata_": {"label": "To be deleted"},
        },
    )
    assert create_res.status_code == 201
    col_id = create_res.json()["id"]

    # Delete (soft delete)
    del_res = await async_client.delete(f"/v1/collections/{col_id}", headers=auth_headers)
    assert del_res.status_code == 204

    # Detail GET returns 404 for deleted
    get_res = await async_client.get(f"/v1/collections/{col_id}", headers=auth_headers)
    assert get_res.status_code == 404

    # List trash
    trash_res = await async_client.get("/v1/collections/trash/list", headers=auth_headers)
    assert trash_res.status_code == 200
    trash_ids = [c["id"] for c in trash_res.json()]
    assert col_id in trash_ids

    # Restore
    rest_res = await async_client.post(f"/v1/collections/{col_id}/restore", headers=auth_headers)
    assert rest_res.status_code == 200

    # Detail GET works again
    get_after = await async_client.get(f"/v1/collections/{col_id}", headers=auth_headers)
    assert get_after.status_code == 200
    assert get_after.json()["id"] == col_id


@pytest.mark.asyncio
async def test_collection_subtypes_and_schema(
    async_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    # 1. Create a subtype for collection
    st_name = f"sub_{uuid.uuid4().hex[:8]}"
    subtype_res = await async_client.post(
        "/v1/record-subtypes",
        headers=auth_headers,
        json={
            "primary_type": "collection",
            "name": st_name,
            "label": {"de": "Fotobestand", "en": "Photo collection"},
            "description": "Fotosammlungen",
            "sort_order": 1,
            "is_default": False,
        },
    )
    assert subtype_res.status_code == 201

    # 2. Create collection with that subtype
    col_res = await async_client.post(
        "/v1/collections",
        headers=auth_headers,
        json={
            "idno": f"COL-{uuid.uuid4().hex[:10]}",
            "collection_type": st_name,
            "status": "draft",
            "metadata_": {"label": "Photos of 1920"},
        },
    )
    assert col_res.status_code == 201
    assert col_res.json()["collection_type"] == st_name

    # 3. Create collection with non-existent subtype fails
    invalid_st_res = await async_client.post(
        "/v1/collections",
        headers=auth_headers,
        json={
            "idno": f"COL-{uuid.uuid4().hex[:10]}",
            "collection_type": "non_existent_subtype",
            "status": "draft",
            "metadata_": {"label": "Should fail"},
        },
    )
    assert invalid_st_res.status_code == 422


@pytest.mark.asyncio
async def test_collection_create_rejects_idno_violating_configured_pattern(
    async_client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Regression test: validate_idno_pattern(pattern, idno) must not be called with
    swapped arguments, or a manually supplied idno that violates the configured
    pattern would be silently accepted."""
    config_res = await async_client.put(
        "/v1/admin/config",
        headers=auth_headers,
        json={"idno_patterns": {"collection": r"^COL-\d{4}$"}},
    )
    assert config_res.status_code == 200

    invalid_res = await async_client.post(
        "/v1/collections",
        headers=auth_headers,
        json={
            "idno": f"NOPE-{uuid.uuid4().hex[:8]}",
            "status": "draft",
            "metadata_": {},
        },
    )
    assert invalid_res.status_code == 422

    valid_idno = f"COL-{uuid.uuid4().int % 10000:04d}"
    valid_res = await async_client.post(
        "/v1/collections",
        headers=auth_headers,
        json={
            "idno": valid_idno,
            "status": "draft",
            "metadata_": {},
        },
    )
    assert valid_res.status_code == 201

    await async_client.put(
        "/v1/admin/config",
        headers=auth_headers,
        json={"idno_patterns": {}},
    )
