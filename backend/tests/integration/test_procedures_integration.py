import uuid


async def test_procedure_crud_and_active_loan_out_guard(async_client, auth_headers) -> None:
    object_response = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"OBJ-{uuid.uuid4().hex[:12]}",
            "status": "draft",
            "object_type": "objekt",
            "metadata_": {"label": "Loan object"},
        },
    )
    assert object_response.status_code == 201
    object_id = object_response.json()["id"]

    first_response = await async_client.post(
        "/v1/procedures",
        headers=auth_headers,
        json={
            "idno": f"PRO-{uuid.uuid4().hex[:12]}",
            "procedure_type": "loan_out",
            "status": "active",
            "due_date": "2026-12-31",
            "metadata_": {"label": "First loan", "note": "First loan"},
        },
    )
    assert first_response.status_code == 201
    first_id = first_response.json()["id"]

    relation_response = await async_client.post(
        "/v1/relations",
        headers=auth_headers,
        json={
            "from_type": "procedure",
            "from_id": first_id,
            "to_type": "object",
            "to_id": object_id,
            "relation_type": "contains",
            "metadata_": {},
        },
    )
    assert relation_response.status_code == 201

    second_response = await async_client.post(
        "/v1/procedures",
        headers=auth_headers,
        json={
            "idno": f"PRO-{uuid.uuid4().hex[:12]}",
            "procedure_type": "loan_out",
            "status": "active",
            "metadata_": {"label": "Second loan", "note": "Second loan"},
        },
    )
    assert second_response.status_code == 201
    second_id = second_response.json()["id"]

    conflict_response = await async_client.post(
        "/v1/relations",
        headers=auth_headers,
        json={
            "from_type": "procedure",
            "from_id": second_id,
            "to_type": "object",
            "to_id": object_id,
            "relation_type": "contains",
            "metadata_": {},
        },
    )
    assert conflict_response.status_code == 409

    complete_response = await async_client.post(
        f"/v1/procedures/{first_id}/complete",
        headers=auth_headers,
        json={"collection_status": "active"},
    )
    assert complete_response.status_code == 200
    assert complete_response.json()["status"] == "completed"

    object_get_response = await async_client.get(f"/v1/objects/{object_id}", headers=auth_headers)
    assert object_get_response.status_code == 200
    assert object_get_response.json()["collection_status"] == "active"

    retry_response = await async_client.post(
        "/v1/relations",
        headers=auth_headers,
        json={
            "from_type": "procedure",
            "from_id": second_id,
            "to_type": "object",
            "to_id": object_id,
            "relation_type": "contains",
            "metadata_": {},
        },
    )
    assert retry_response.status_code == 201

    update_response = await async_client.put(
        f"/v1/procedures/{second_id}",
        headers=auth_headers,
        json={
            "idno": second_response.json()["idno"],
            "procedure_type": "loan_out",
            "status": "completed",
            "metadata_": {"label": "Second loan", "note": "Done"},
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "completed"
