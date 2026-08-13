import asyncio
import uuid

from sqlalchemy import select

from katalon.core.models import FieldDefinition, FormVariant, FormVariantRoleDefault


async def test_procedure_crud_and_active_loan_out_guard(async_client, auth_headers) -> None:
    object_response = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"OBJ-{uuid.uuid4().hex[:12]}",
            "status": "draft",
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


async def test_procedure_validation_uses_procedure_type_schema(async_client, auth_headers) -> None:
    field_name = f"restoration_note_{uuid.uuid4().hex[:8]}"
    field_response = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "procedure",
            "target_subtype": "conservation",
            "name": field_name,
            "label": {"de": "Restaurierungsnotiz"},
            "field_type": "text",
            "is_required": True,
            "is_repeatable": False,
        },
    )
    assert field_response.status_code == 201, field_response.text

    missing_response = await async_client.post(
        "/v1/procedures",
        headers=auth_headers,
        json={
            "idno": f"PRO-{uuid.uuid4().hex[:12]}",
            "procedure_type": "conservation",
            "status": "active",
            "metadata_": {"label": "Restaurierung"},
        },
    )
    assert missing_response.status_code == 422
    assert field_name in str(missing_response.json()["detail"])

    draft_response = await async_client.post(
        "/v1/procedures",
        headers=auth_headers,
        json={
            "idno": f"PRO-{uuid.uuid4().hex[:12]}",
            "procedure_type": "conservation",
            "status": "draft",
            "metadata_": {"label": "Restaurierung"},
        },
    )
    assert draft_response.status_code == 201, draft_response.text

    ok_response = await async_client.post(
        "/v1/procedures",
        headers=auth_headers,
        json={
            "idno": f"PRO-{uuid.uuid4().hex[:12]}",
            "procedure_type": "conservation",
            "status": "active",
            "metadata_": {"label": "Restaurierung", field_name: "gereinigt"},
        },
    )
    assert ok_response.status_code == 201, ok_response.text


async def test_procedure_subtypes_are_configurable_and_unused_types_can_be_retired(
    async_client, auth_headers
) -> None:
    subtypes_response = await async_client.get(
        "/v1/record-subtypes?primary_type=procedure", headers=auth_headers
    )
    assert subtypes_response.status_code == 200, subtypes_response.text
    system_subtypes = {subtype["name"]: subtype for subtype in subtypes_response.json()}
    assert {"loan_out", "loan_in", "acquisition", "conservation", "object_entry", "deaccession"} <= set(
        system_subtypes
    )

    custom_type = f"custom_procedure_{uuid.uuid4().hex[:8]}"
    created_subtype = await async_client.post(
        "/v1/record-subtypes",
        headers=auth_headers,
        json={
            "primary_type": "procedure",
            "name": custom_type,
            "label": {"de": "Eigener Vorgang"},
            "description": "Für einen lokalen Arbeitsablauf.",
        },
    )
    assert created_subtype.status_code == 201, created_subtype.text
    assert created_subtype.json()["description"] == "Für einen lokalen Arbeitsablauf."

    field_name = f"custom_procedure_note_{uuid.uuid4().hex[:8]}"
    created_field = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "procedure",
            "target_subtype": custom_type,
            "name": field_name,
            "label": {"de": "Notiz"},
            "field_type": "text",
            "is_required": True,
        },
    )
    assert created_field.status_code == 201, created_field.text

    variant = await async_client.post(
        "/v1/form-variants",
        headers=auth_headers,
        json={
            "target_type": "procedure",
            "target_subtype": custom_type,
            "name": "Eigene Erfassung",
            "field_names": ["label", field_name],
        },
    )
    assert variant.status_code == 201, variant.text

    missing_required = await async_client.post(
        "/v1/procedures",
        headers=auth_headers,
        json={
            "idno": f"PRO-{uuid.uuid4().hex[:12]}",
            "procedure_type": custom_type,
            "status": "active",
            "metadata_": {"label": "Eigener Vorgang"},
        },
    )
    assert missing_required.status_code == 422

    created_procedure = await async_client.post(
        "/v1/procedures",
        headers=auth_headers,
        json={
            "idno": f"PRO-{uuid.uuid4().hex[:12]}",
            "procedure_type": custom_type,
            "status": "active",
            "metadata_": {"label": "Eigener Vorgang", field_name: "vorhanden"},
        },
    )
    assert created_procedure.status_code == 201, created_procedure.text

    delete_in_use = await async_client.delete(
        f"/v1/record-subtypes/{created_subtype.json()['id']}", headers=auth_headers
    )
    assert delete_in_use.status_code == 409

    retired_type = system_subtypes["object_entry"]
    field_response = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "procedure",
            "target_subtype": "object_entry",
            "name": f"entry_note_{uuid.uuid4().hex[:8]}",
            "label": {"de": "Eingangsnotiz"},
            "field_type": "text",
        },
    )
    assert field_response.status_code == 201, field_response.text
    field_id = uuid.UUID(field_response.json()["id"])

    variant_response = await async_client.post(
        "/v1/form-variants",
        headers=auth_headers,
        json={
            "target_type": "procedure",
            "target_subtype": "object_entry",
            "name": "Eingangserfassung",
            "field_names": ["label", field_response.json()["name"]],
        },
    )
    assert variant_response.status_code == 201, variant_response.text
    variant_id = uuid.UUID(variant_response.json()["id"])
    default_response = await async_client.post(
        f"/v1/form-variants/{variant_id}/role-defaults/admin", headers=auth_headers
    )
    assert default_response.status_code == 204

    delete_unused = await async_client.delete(
        f"/v1/record-subtypes/{retired_type['id']}", headers=auth_headers
    )
    assert delete_unused.status_code == 204, delete_unused.text

    from katalon.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        assert (await db.get(FieldDefinition, field_id)).is_deleted is True
        assert (await db.get(FormVariant, variant_id)).is_deleted is True
        defaults = await db.execute(
            select(FormVariantRoleDefault).where(FormVariantRoleDefault.variant_id == variant_id)
        )
        assert defaults.scalars().all() == []


async def test_procedures_do_not_expose_snapshot_routes(app) -> None:
    paths = app.openapi()["paths"]
    assert "/v1/procedures/{procedure_id}/snapshots" not in paths
    assert "/v1/procedures/{procedure_id}/snapshots/{snapshot_id}/restore" not in paths


async def test_concurrent_active_loan_relations_allow_one_winner(
    async_client, auth_headers
) -> None:
    object_response = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"OBJ-{uuid.uuid4().hex[:12]}",
            "status": "draft",
            "metadata_": {},
        },
    )
    object_id = object_response.json()["id"]

    procedure_ids = []
    for _ in range(2):
        response = await async_client.post(
            "/v1/procedures",
            headers=auth_headers,
            json={
                "idno": f"PRO-{uuid.uuid4().hex[:12]}",
                "procedure_type": "loan_out",
                "status": "active",
                "metadata_": {"label": "Concurrent loan"},
            },
        )
        assert response.status_code == 201, response.text
        procedure_ids.append(response.json()["id"])

    async def link(procedure_id: str):
        return await async_client.post(
            "/v1/relations",
            headers=auth_headers,
            json={
                "from_type": "procedure",
                "from_id": procedure_id,
                "to_type": "object",
                "to_id": object_id,
                "relation_type": "contains",
                "metadata_": {},
            },
        )

    responses = await asyncio.gather(*(link(procedure_id) for procedure_id in procedure_ids))
    assert sorted(response.status_code for response in responses) == [201, 409]
