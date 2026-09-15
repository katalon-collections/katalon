# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid

import pytest

from katalon import database
from katalon.core.models import StorageLocation
from katalon.services.storage_location_service import get_storage_location_subtree_ids


@pytest.mark.asyncio
async def test_storage_location_subtree_ids(app) -> None:
    async with database.AsyncSessionLocal() as db_session:
        # Building -> Room -> Shelf
        building = StorageLocation(
            idno=f"BLD-{uuid.uuid4().hex[:6]}", metadata_={"label": "Gebäude A"}
        )
        db_session.add(building)
        await db_session.flush()

        room = StorageLocation(
            idno=f"ROOM-{uuid.uuid4().hex[:6]}",
            parent_id=building.id,
            metadata_={"label": "Raum 101"},
        )
        db_session.add(room)
        await db_session.flush()

        shelf = StorageLocation(
            idno=f"SHELF-{uuid.uuid4().hex[:6]}", parent_id=room.id, metadata_={"label": "Regal 1"}
        )
        db_session.add(shelf)
        await db_session.flush()

        other = StorageLocation(
            idno=f"OTHER-{uuid.uuid4().hex[:6]}", metadata_={"label": "Anderer Ort"}
        )
        db_session.add(other)
        await db_session.flush()

        bld_ids = await get_storage_location_subtree_ids(db_session, building.id)
        assert set(bld_ids) == {building.id, room.id, shelf.id}
        assert other.id not in bld_ids

        room_ids = await get_storage_location_subtree_ids(db_session, room.id)
        assert set(room_ids) == {room.id, shelf.id}

        shelf_ids = await get_storage_location_subtree_ids(db_session, shelf.id)
        assert shelf_ids == [shelf.id]


@pytest.mark.asyncio
async def test_storage_location_objects_endpoint_and_filter(async_client, auth_headers) -> None:
    # 1. Create Building -> Room
    bld_res = await async_client.post(
        "/v1/storage-locations",
        headers=auth_headers,
        json={"idno": f"BLD-{uuid.uuid4().hex[:6]}", "metadata_": {"label": "Hauptdepot"}},
    )
    assert bld_res.status_code == 201, bld_res.text
    bld_id = bld_res.json()["id"]

    room_res = await async_client.post(
        "/v1/storage-locations",
        headers=auth_headers,
        json={
            "idno": f"ROOM-{uuid.uuid4().hex[:6]}",
            "parent_id": bld_id,
            "metadata_": {"label": "Depotraum 1"},
        },
    )
    assert room_res.status_code == 201, room_res.text
    room_id = room_res.json()["id"]

    # 2. Create objects
    obj_bld_res = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"OBJ-{uuid.uuid4().hex[:10]}",
            "status": "public",
            "metadata_": {"label": "Objekt im Gebäude"},
        },
    )
    assert obj_bld_res.status_code == 201, obj_bld_res.text
    obj_bld_id = obj_bld_res.json()["id"]

    obj_room_res = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"OBJ-{uuid.uuid4().hex[:10]}",
            "status": "public",
            "metadata_": {"label": "Objekt im Raum"},
        },
    )
    assert obj_room_res.status_code == 201, obj_room_res.text
    obj_room_id = obj_room_res.json()["id"]
    rel1 = await async_client.post(
        "/v1/relations",
        headers=auth_headers,
        json={
            "from_type": "object",
            "from_id": obj_bld_id,
            "to_type": "storage_location",
            "to_id": bld_id,
            "relation_type": "current_location",
        },
    )
    assert rel1.status_code == 201, rel1.text

    rel2 = await async_client.post(
        "/v1/relations",
        headers=auth_headers,
        json={
            "from_type": "object",
            "from_id": obj_room_id,
            "to_type": "storage_location",
            "to_id": room_id,
            "relation_type": "current_location",
        },
    )
    assert rel2.status_code == 201, rel2.text

    # 4. Query /v1/storage-locations/{id}/objects?include_sublocations=false on Building
    res_direct = await async_client.get(
        f"/v1/storage-locations/{bld_id}/objects?include_sublocations=false",
        headers=auth_headers,
    )
    assert res_direct.status_code == 200
    direct_data = res_direct.json()
    assert direct_data["total"] == 1
    assert direct_data["items"][0]["id"] == obj_bld_id

    # 5. Query /v1/storage-locations/{id}/objects?include_sublocations=true on Building
    res_sub = await async_client.get(
        f"/v1/storage-locations/{bld_id}/objects?include_sublocations=true",
        headers=auth_headers,
    )
    assert res_sub.status_code == 200
    sub_data = res_sub.json()
    assert sub_data["total"] == 2
    found_ids = {item["id"] for item in sub_data["items"]}
    assert found_ids == {obj_bld_id, obj_room_id}

    # 6. Query /v1/objects?storage_location_id={bld_id}&include_sublocations=true
    obj_list_sub = await async_client.get(
        f"/v1/objects?storage_location_id={bld_id}&include_sublocations=true",
        headers=auth_headers,
    )
    assert obj_list_sub.status_code == 200
    obj_sub_ids = {item["id"] for item in obj_list_sub.json()["items"]}
    assert obj_bld_id in obj_sub_ids
    assert obj_room_id in obj_sub_ids

    # 7. Query /v1/objects?storage_location_id={bld_id}&include_sublocations=false
    obj_list_direct = await async_client.get(
        f"/v1/objects?storage_location_id={bld_id}&include_sublocations=false",
        headers=auth_headers,
    )
    assert obj_list_direct.status_code == 200
    obj_direct_ids = {item["id"] for item in obj_list_direct.json()["items"]}
    assert obj_bld_id in obj_direct_ids
    assert obj_room_id not in obj_direct_ids

    # 8. Query /v1/relations?to_type=storage_location&to_id={bld_id}&include_sublocations=true
    rel_sub = await async_client.get(
        f"/v1/relations?to_type=storage_location&to_id={bld_id}&include_sublocations=true",
        headers=auth_headers,
    )
    assert rel_sub.status_code == 200
    rel_found_objs = {r["from_id"] for r in rel_sub.json()}
    assert {obj_bld_id, obj_room_id}.issubset(rel_found_objs)


@pytest.mark.asyncio
async def test_storage_location_delete_blocks_cascades_and_reparents(
    async_client, auth_headers
) -> None:
    # Building -> Room -> Shelf
    bld_res = await async_client.post(
        "/v1/storage-locations",
        headers=auth_headers,
        json={"idno": f"BLD-{uuid.uuid4().hex[:6]}", "metadata_": {"label": "Depot"}},
    )
    assert bld_res.status_code == 201, bld_res.text
    bld_id = bld_res.json()["id"]

    room_res = await async_client.post(
        "/v1/storage-locations",
        headers=auth_headers,
        json={
            "idno": f"ROOM-{uuid.uuid4().hex[:6]}",
            "parent_id": bld_id,
            "metadata_": {"label": "Raum"},
        },
    )
    assert room_res.status_code == 201, room_res.text
    room_id = room_res.json()["id"]

    shelf_res = await async_client.post(
        "/v1/storage-locations",
        headers=auth_headers,
        json={
            "idno": f"SHELF-{uuid.uuid4().hex[:6]}",
            "parent_id": room_id,
            "metadata_": {"label": "Regal"},
        },
    )
    assert shelf_res.status_code == 201, shelf_res.text
    shelf_id = shelf_res.json()["id"]

    # Deleting the building is blocked by default — it still has a child room.
    blocked = await async_client.delete(f"/v1/storage-locations/{bld_id}", headers=auth_headers)
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"]["child_count"] == 1

    # Reparent moves the room up (building -> None) instead of orphaning it silently.
    reparented = await async_client.delete(
        f"/v1/storage-locations/{bld_id}",
        headers=auth_headers,
        params={"reparent": "true"},
    )
    assert reparented.status_code == 204, reparented.text
    room_after = await async_client.get(f"/v1/storage-locations/{room_id}", headers=auth_headers)
    assert room_after.status_code == 200, room_after.text
    assert room_after.json()["parent_id"] is None

    # Cascade removes the whole remaining subtree (room + shelf) in one call.
    cascade_blocked = await async_client.delete(
        f"/v1/storage-locations/{room_id}", headers=auth_headers
    )
    assert cascade_blocked.status_code == 409, cascade_blocked.text
    assert cascade_blocked.json()["detail"]["child_count"] == 1

    cascade_deleted = await async_client.delete(
        f"/v1/storage-locations/{room_id}",
        headers=auth_headers,
        params={"cascade": "true"},
    )
    assert cascade_deleted.status_code == 204, cascade_deleted.text
    shelf_after = await async_client.get(f"/v1/storage-locations/{shelf_id}", headers=auth_headers)
    assert shelf_after.status_code == 404, shelf_after.text

    # cascade and reparent are mutually exclusive.
    conflict = await async_client.delete(
        f"/v1/storage-locations/{bld_id}",
        headers=auth_headers,
        params={"cascade": "true", "reparent": "true"},
    )
    assert conflict.status_code == 400, conflict.text
