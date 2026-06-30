import uuid

import pytest


@pytest.mark.asyncio
async def test_object_crud_roundtrip(async_client, auth_headers) -> None:
    idno = f"INT-{uuid.uuid4().hex[:12]}"

    create_response = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": idno,
            "status": "draft",
            "object_type": "objekt",
            "metadata_": {"label": "Integration object"},
        },
    )
    assert create_response.status_code == 201

    created = create_response.json()
    object_id = created["id"]
    assert created["idno"] == idno
    assert created["status"] == "draft"

    get_response = await async_client.get(f"/v1/objects/{object_id}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["metadata_"]["label"] == "Integration object"

    update_response = await async_client.put(
        f"/v1/objects/{object_id}",
        headers=auth_headers,
        json={
            "idno": idno,
            "status": "public",
            "object_type": "objekt",
            "metadata_": {"label": "Updated integration object"},
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "public"

    delete_response = await async_client.delete(f"/v1/objects/{object_id}", headers=auth_headers)
    assert delete_response.status_code == 204

    missing_response = await async_client.get(f"/v1/objects/{object_id}", headers=auth_headers)
    assert missing_response.status_code == 404


@pytest.mark.asyncio
async def test_object_draft_allows_missing_required_fields(async_client, auth_headers) -> None:
    field_name = f"title_required_{uuid.uuid4().hex[:8]}"
    field_response = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "object",
            "name": field_name,
            "label": {"de": "Pflichttitel"},
            "field_type": "text",
            "is_required": True,
            "is_repeatable": False,
        },
    )
    assert field_response.status_code == 201, field_response.text

    draft_response = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"OBJ-{uuid.uuid4().hex[:12]}",
            "status": "draft",
            "object_type": "objekt",
            "metadata_": {"label": "Draft object"},
        },
    )
    assert draft_response.status_code == 201, draft_response.text

    public_response = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"OBJ-{uuid.uuid4().hex[:12]}",
            "status": "public",
            "object_type": "objekt",
            "metadata_": {"label": "Public object"},
        },
    )
    assert public_response.status_code == 422
    assert field_name in str(public_response.json()["detail"])
