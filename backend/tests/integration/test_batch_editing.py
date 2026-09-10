# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid

import pytest


@pytest.fixture
def unique_suffix():
    return uuid.uuid4().hex[:12]


async def _create_object(async_client, auth_headers, idno: str, status: str = "draft", metadata: dict | None = None):
    response = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": idno,
            "status": status,
            "metadata_": metadata or {},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_entity(async_client, auth_headers, idno: str, status: str = "draft", metadata: dict | None = None):
    response = await async_client.post(
        "/v1/entities",
        headers=auth_headers,
        json={
            "idno": idno,
            "status": status,
            "metadata_": metadata or {},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_batch_set_status(async_client, auth_headers, unique_suffix):
    obj1 = await _create_object(async_client, auth_headers, f"BATCH-STATUS-1-{unique_suffix}")
    obj2 = await _create_object(async_client, auth_headers, f"BATCH-STATUS-2-{unique_suffix}")

    response = await async_client.post(
        "/v1/batch/object",
        headers=auth_headers,
        json={
            "ids": [obj1["id"], obj2["id"]],
            "operation": {"type": "set_status", "value": "public"},
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["affected"] == 2
    assert result["errors"] == []
    assert result["batch_job_id"] is not None

    for obj_id in (obj1["id"], obj2["id"]):
        obj = (await async_client.get(f"/v1/objects/{obj_id}", headers=auth_headers)).json()
        assert obj["status"] == "public"
        audit = (await async_client.get(f"/v1/objects/{obj_id}/audit-log", headers=auth_headers)).json()
        assert any(entry["action"] == "batch_update" for entry in audit)
        assert any(
            entry.get("changed_fields", {}).get("batch_job_id") == result["batch_job_id"]
            for entry in audit
        )


@pytest.mark.asyncio
async def test_batch_set_field(async_client, auth_headers, unique_suffix):
    obj = await _create_object(
        async_client, auth_headers, f"BATCH-FIELD-{unique_suffix}", metadata={"label": "Before"}
    )

    response = await async_client.post(
        "/v1/batch/object",
        headers=auth_headers,
        json={
            "ids": [obj["id"]],
            "operation": {"type": "set_field", "field": "label", "value": "After"},
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["affected"] == 1
    assert result["errors"] == []

    updated = (await async_client.get(f"/v1/objects/{obj['id']}", headers=auth_headers)).json()
    assert updated["metadata_"]["label"] == "After"


@pytest.mark.asyncio
async def test_batch_append_and_clear_repeatable_field(async_client, auth_headers, unique_suffix):
    field_name = f"keywords_{unique_suffix}"
    schema_response = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "object",
            "name": field_name,
            "label": {"de": "Keywords"},
            "field_type": "text",
            "is_repeatable": True,
        },
    )
    assert schema_response.status_code == 201, schema_response.text

    obj = await _create_object(
        async_client,
        auth_headers,
        f"BATCH-APPEND-{unique_suffix}",
        metadata={field_name: ["alpha"]},
    )

    # Append
    response = await async_client.post(
        "/v1/batch/object",
        headers=auth_headers,
        json={
            "ids": [obj["id"]],
            "operation": {"type": "append_field", "field": field_name, "value": "beta"},
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["affected"] == 1

    updated = (await async_client.get(f"/v1/objects/{obj['id']}", headers=auth_headers)).json()
    assert updated["metadata_"][field_name] == ["alpha", "beta"]

    # Clear
    response = await async_client.post(
        "/v1/batch/object",
        headers=auth_headers,
        json={
            "ids": [obj["id"]],
            "operation": {"type": "clear_field", "field": field_name},
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["affected"] == 1

    updated = (await async_client.get(f"/v1/objects/{obj['id']}", headers=auth_headers)).json()
    assert updated["metadata_"].get(field_name) in (None, "", [])


@pytest.mark.asyncio
async def test_batch_add_and_remove_relation(async_client, auth_headers, unique_suffix):
    obj = await _create_object(async_client, auth_headers, f"BATCH-REL-OBJ-{unique_suffix}")
    entity = await _create_entity(async_client, auth_headers, f"BATCH-REL-ENT-{unique_suffix}")

    response = await async_client.post(
        "/v1/batch/object",
        headers=auth_headers,
        json={
            "ids": [obj["id"]],
            "operation": {
                "type": "add_relation",
                "relation_to_type": "entity",
                "relation_to_id": entity["id"],
                "relation_type": "related_to",
            },
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["affected"] == 1

    relations = (await async_client.get("/v1/relations", headers=auth_headers, params={
        "from_type": "object",
        "from_id": obj["id"],
        "to_type": "entity",
        "to_id": entity["id"],
    })).json()
    assert len(relations) == 1
    assert relations[0]["relation_type"] == "related_to"

    # Remove
    response = await async_client.post(
        "/v1/batch/object",
        headers=auth_headers,
        json={
            "ids": [obj["id"]],
            "operation": {
                "type": "remove_relation",
                "relation_to_type": "entity",
                "relation_to_id": entity["id"],
                "relation_type": "related_to",
            },
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["affected"] == 1

    relations = (await async_client.get("/v1/relations", headers=auth_headers, params={
        "from_type": "object",
        "from_id": obj["id"],
    })).json()
    assert relations == []


@pytest.mark.asyncio
async def test_batch_via_filters_cross_page(async_client, auth_headers, unique_suffix):
    created = []
    for i in range(5):
        obj = await _create_object(
            async_client,
            auth_headers,
            f"BATCH-FILTER-{i}-{unique_suffix}",
            metadata={"label": f"Cross-page target {unique_suffix}"},
        )
        created.append(obj["id"])

    # Also create an object that does not match the query.
    await _create_object(
        async_client,
        auth_headers,
        f"BATCH-FILTER-OTHER-{unique_suffix}",
        metadata={"label": "Other label"},
    )

    response = await async_client.post(
        "/v1/batch/object",
        headers=auth_headers,
        json={
            "filters": {"q": f"Cross-page target {unique_suffix}"},
            "operation": {"type": "set_status", "value": "internal"},
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["affected"] == 5
    assert result["errors"] == []

    for obj_id in created:
        obj = (await async_client.get(f"/v1/objects/{obj_id}", headers=auth_headers)).json()
        assert obj["status"] == "internal"


@pytest.mark.asyncio
async def test_batch_invalid_field_returns_error(async_client, auth_headers, unique_suffix):
    obj = await _create_object(async_client, auth_headers, f"BATCH-ERR-{unique_suffix}")

    response = await async_client.post(
        "/v1/batch/object",
        headers=auth_headers,
        json={
            "ids": [obj["id"]],
            "operation": {"type": "set_field", "field": "does_not_exist", "value": "x"},
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["affected"] == 0
    assert len(result["errors"]) == 1
    assert "does_not_exist" in result["errors"][0]


@pytest.mark.asyncio
async def test_batch_requires_update_permission(async_client, auth_headers, unique_suffix):
    # A viewer user never has update permission.
    user_response = await async_client.post(
        "/v1/users",
        headers=auth_headers,
        json={"email": f"viewer-{unique_suffix}@katalon.dev", "password": "Viewer1234", "role": "viewer"},
    )
    assert user_response.status_code == 201, user_response.text

    viewer_token = (await async_client.post(
        "/v1/auth/token",
        data={"username": f"viewer-{unique_suffix}@katalon.dev", "password": "Viewer1234"},
    )).json()["access_token"]
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    obj = await _create_object(async_client, auth_headers, f"BATCH-PERM-{unique_suffix}")

    response = await async_client.post(
        "/v1/batch/object",
        headers=viewer_headers,
        json={
            "ids": [obj["id"]],
            "operation": {"type": "set_status", "value": "public"},
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_batch_async_path_for_large_set(async_client, auth_headers, unique_suffix):
    ids = []
    for i in range(101):
        obj = await _create_object(
            async_client,
            auth_headers,
            f"BATCH-ASYNC-{i}-{unique_suffix}",
        )
        ids.append(obj["id"])

    response = await async_client.post(
        "/v1/batch/object",
        headers=auth_headers,
        json={
            "ids": ids,
            "operation": {"type": "set_status", "value": "public"},
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["task_id"] is not None
    assert result["batch_job_id"] is not None
