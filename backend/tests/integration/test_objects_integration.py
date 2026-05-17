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
