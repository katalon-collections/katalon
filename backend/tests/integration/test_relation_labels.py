# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Issue #324: relation list endpoints must resolve display labels, not raw UUIDs."""

import uuid


async def test_admin_relations_resolve_display_labels(async_client, auth_headers) -> None:
    object_response = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"OBJ-{uuid.uuid4().hex[:12]}",
            "status": "draft",
            "metadata_": {"label": "Fotografie Marrakesch"},
        },
    )
    assert object_response.status_code == 201, object_response.text
    object_id = object_response.json()["id"]

    entity_response = await async_client.post(
        "/v1/entities",
        headers=auth_headers,
        json={
            "idno": f"ENT-{uuid.uuid4().hex[:12]}",
            "status": "draft",
            "metadata_": {"label": "Merian"},
        },
    )
    assert entity_response.status_code == 201
    entity_id = entity_response.json()["id"]

    relation_response = await async_client.post(
        "/v1/relations",
        headers=auth_headers,
        json={
            "from_type": "object",
            "from_id": object_id,
            "to_type": "entity",
            "to_id": entity_id,
            "relation_type": "depicts",
            "metadata_": {},
        },
    )
    assert relation_response.status_code == 201

    list_response = await async_client.get(
        "/v1/relations", headers=auth_headers, params={"from_type": "object", "from_id": object_id},
    )
    assert list_response.status_code == 200
    relations = list_response.json()
    assert len(relations) == 1
    rel = relations[0]
    assert rel["from_label"] == "Fotografie Marrakesch"
    assert rel["to_label"] == "Merian"
    # Never a raw UUID standing in for an unresolved label.
    assert rel["to_label"] != entity_id


async def test_admin_relation_to_missing_record_has_no_label(async_client, auth_headers) -> None:
    """A relation pointing at a non-existent (e.g. since-deleted) record gets label=None,
    distinct from a resolvable title."""
    object_response = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"OBJ-{uuid.uuid4().hex[:12]}",
            "status": "draft",
            "metadata_": {"label": "Verwaistes Objekt"},
        },
    )
    assert object_response.status_code == 201, object_response.text
    object_id = object_response.json()["id"]

    missing_entity_id = str(uuid.uuid4())

    relation_response = await async_client.post(
        "/v1/relations",
        headers=auth_headers,
        json={
            "from_type": "object",
            "from_id": object_id,
            "to_type": "entity",
            "to_id": missing_entity_id,
            "relation_type": "depicts",
            "metadata_": {},
        },
    )
    assert relation_response.status_code == 201

    list_response = await async_client.get(
        "/v1/relations", headers=auth_headers, params={"from_type": "object", "from_id": object_id},
    )
    assert list_response.status_code == 200
    rel = list_response.json()[0]
    assert rel["from_label"] == "Verwaistes Objekt"
    assert rel["to_label"] is None


async def test_portal_relations_resolve_labels_for_public_records(async_client, auth_headers) -> None:
    object_response = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"OBJ-{uuid.uuid4().hex[:12]}",
            "status": "public",
            "metadata_": {"label": "Öffentliches Objekt"},
        },
    )
    assert object_response.status_code == 201, object_response.text
    object_id = object_response.json()["id"]

    entity_response = await async_client.post(
        "/v1/entities",
        headers=auth_headers,
        json={
            "idno": f"ENT-{uuid.uuid4().hex[:12]}",
            "status": "public",
            "metadata_": {"label": "Merian"},
        },
    )
    entity_id = entity_response.json()["id"]

    relation_response = await async_client.post(
        "/v1/relations",
        headers=auth_headers,
        json={
            "from_type": "object",
            "from_id": object_id,
            "to_type": "entity",
            "to_id": entity_id,
            "relation_type": "depicts",
            "metadata_": {},
        },
    )
    assert relation_response.status_code == 201

    portal_response = await async_client.get(
        "/portal/v1/relations", params={"from_type": "object", "from_id": object_id},
    )
    assert portal_response.status_code == 200
    relations = portal_response.json()
    assert len(relations) == 1
    assert relations[0]["from_label"] == "Öffentliches Objekt"
    assert relations[0]["to_label"] == "Merian"


async def test_portal_relations_exclude_non_public_endpoint_entirely(async_client, auth_headers) -> None:
    """Non-public target: relation is excluded (permission), not returned with a null label (display bug)."""
    object_response = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"OBJ-{uuid.uuid4().hex[:12]}",
            "status": "public",
            "metadata_": {"label": "Öffentliches Objekt 2"},
        },
    )
    assert object_response.status_code == 201, object_response.text
    object_id = object_response.json()["id"]

    entity_response = await async_client.post(
        "/v1/entities",
        headers=auth_headers,
        json={
            "idno": f"ENT-{uuid.uuid4().hex[:12]}",
            "status": "draft",
            "metadata_": {"label": "Nicht öffentlich"},
        },
    )
    entity_id = entity_response.json()["id"]

    relation_response = await async_client.post(
        "/v1/relations",
        headers=auth_headers,
        json={
            "from_type": "object",
            "from_id": object_id,
            "to_type": "entity",
            "to_id": entity_id,
            "relation_type": "depicts",
            "metadata_": {},
        },
    )
    assert relation_response.status_code == 201

    portal_response = await async_client.get(
        "/portal/v1/relations", params={"from_type": "object", "from_id": object_id},
    )
    assert portal_response.status_code == 200
    assert portal_response.json() == []
