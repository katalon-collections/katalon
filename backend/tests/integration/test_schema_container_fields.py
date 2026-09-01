# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Integration tests for group/container field creation and listing.

Regression tests for MissingGreenlet errors caused by lazy-loading the
`children` relationship outside an async SQLAlchemy context.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_schema_returns_200(async_client: AsyncClient, auth_headers: dict) -> None:
    r = await async_client.get("/v1/schema/object", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_list_procedure_schema_accepts_builtin_subtype(async_client: AsyncClient, auth_headers: dict) -> None:
    r = await async_client.get("/v1/schema/procedure?subtype=conservation", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert any(f["name"] == "label" for f in r.json())


@pytest.mark.asyncio
async def test_create_group_field_no_500(async_client: AsyncClient, auth_headers: dict) -> None:
    r = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "object",
            "name": "test_group_field",
            "label": {"de": "Testgruppe", "en": "Test Group"},
            "field_type": "group",
            "is_required": False,
            "is_repeatable": True,
            "sort_order": 99,
            "settings": {},
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["field_type"] == "group"
    assert data["children"] == []


@pytest.mark.asyncio
async def test_create_sub_field_under_group(async_client: AsyncClient, auth_headers: dict) -> None:
    # Create parent group
    group_r = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "object",
            "name": "test_container_for_sub",
            "label": {"de": "Container"},
            "field_type": "group",
            "is_required": False,
            "is_repeatable": True,
            "sort_order": 98,
            "settings": {},
        },
    )
    assert group_r.status_code == 201, group_r.text
    group_id = group_r.json()["id"]

    # Create sub-field under the group
    sub_r = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "object",
            "name": "test_sub_field",
            "label": {"de": "Unterfeld", "en": "Sub Field"},
            "field_type": "text",
            "is_required": True,
            "is_repeatable": False,
            "sort_order": 0,
            "settings": {},
            "parent_id": group_id,
        },
    )
    assert sub_r.status_code == 201, sub_r.text
    sub_data = sub_r.json()
    assert sub_data["parent_id"] == group_id


@pytest.mark.asyncio
async def test_create_authority_sub_field_under_group(
    async_client: AsyncClient, auth_headers: dict
) -> None:
    group_r = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "object",
            "name": "authority_container",
            "label": {"de": "Normierte Materialien"},
            "field_type": "group",
            "is_repeatable": True,
            "settings": {},
        },
    )
    assert group_r.status_code == 201, group_r.text

    sub_r = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "object",
            "name": "authority_material",
            "label": {"de": "Material"},
            "field_type": "authority",
            "is_repeatable": False,
            "settings": {"source": "gnd"},
            "parent_id": group_r.json()["id"],
        },
    )
    assert sub_r.status_code == 201, sub_r.text
    assert sub_r.json()["settings"] == {"source": "gnd"}


@pytest.mark.asyncio
async def test_list_schema_embeds_children(async_client: AsyncClient, auth_headers: dict) -> None:
    # Create group
    group_r = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "entity",
            "name": "embed_test_group",
            "label": {"de": "Einbettungstest"},
            "field_type": "group",
            "is_required": False,
            "is_repeatable": True,
            "sort_order": 99,
            "settings": {},
        },
    )
    assert group_r.status_code == 201, group_r.text
    group_id = group_r.json()["id"]

    # Create sub-field
    await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "entity",
            "name": "embed_test_sub",
            "label": {"de": "Unterfeld"},
            "field_type": "text",
            "is_required": False,
            "is_repeatable": False,
            "sort_order": 0,
            "settings": {},
            "parent_id": group_id,
        },
    )

    # List schema — group must have the sub-field embedded in children
    list_r = await async_client.get("/v1/schema/entity", headers=auth_headers)
    assert list_r.status_code == 200, list_r.text
    fields = list_r.json()

    group = next((f for f in fields if f["name"] == "embed_test_group"), None)
    assert group is not None, "group field not found in schema list"
    assert len(group["children"]) == 1
    assert group["children"][0]["name"] == "embed_test_sub"


@pytest.mark.asyncio
async def test_reset_schema_soft_deletes_all_custom_fields(async_client: AsyncClient, auth_headers: dict) -> None:
    field_r = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "place", "name": "reset_test_field", "label": {"de": "Reset-Test"},
            "field_type": "text", "is_required": False, "is_repeatable": False, "settings": {},
        },
    )
    assert field_r.status_code == 201, field_r.text

    summary_r = await async_client.get("/v1/schema/place/reset-summary", headers=auth_headers)
    assert summary_r.status_code == 200, summary_r.text
    assert summary_r.json()["deletable_fields"] >= 1

    reset_r = await async_client.post("/v1/schema/place/reset", headers=auth_headers)
    assert reset_r.status_code == 200, reset_r.text
    assert reset_r.json()["deleted_fields"] >= 1

    fields_r = await async_client.get("/v1/schema/place", headers=auth_headers)
    assert fields_r.status_code == 200, fields_r.text
    assert all(field["name"] != "reset_test_field" for field in fields_r.json())
    assert any(field["name"] == "label" for field in fields_r.json())


@pytest.mark.asyncio
async def test_reset_schema_only_soft_deletes_selected_subtype(async_client: AsyncClient, auth_headers: dict) -> None:
    for name, subtype in (("reset_conservation", "conservation"), ("reset_acquisition", "acquisition")):
        field_r = await async_client.post(
            "/v1/schema",
            headers=auth_headers,
            json={
                "target_type": "procedure", "target_subtype": subtype, "name": name,
                "label": {"de": name}, "field_type": "text", "is_required": False,
                "is_repeatable": False, "settings": {},
            },
        )
        assert field_r.status_code == 201, field_r.text

    reset_r = await async_client.post(
        "/v1/schema/procedure/reset?subtype=conservation", headers=auth_headers
    )
    assert reset_r.status_code == 200, reset_r.text

    fields_r = await async_client.get("/v1/schema/procedure?subtype=acquisition", headers=auth_headers)
    assert fields_r.status_code == 200, fields_r.text
    assert any(field["name"] == "reset_acquisition" for field in fields_r.json())


@pytest.mark.asyncio
async def test_nested_group_rejected(async_client: AsyncClient, auth_headers: dict) -> None:
    # Create a group field
    group_r = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "object",
            "name": "outer_group_nesting_test",
            "label": {"de": "Äußere Gruppe"},
            "field_type": "group",
            "is_required": False,
            "is_repeatable": True,
            "sort_order": 97,
            "settings": {},
        },
    )
    assert group_r.status_code == 201, group_r.text
    group_id = group_r.json()["id"]

    # Attempting to create a nested group must be rejected
    nested_r = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "object",
            "name": "inner_group_nesting_test",
            "label": {"de": "Innere Gruppe"},
            "field_type": "group",
            "is_required": False,
            "is_repeatable": True,
            "sort_order": 0,
            "settings": {},
            "parent_id": group_id,
        },
    )
    assert nested_r.status_code == 422


@pytest.mark.asyncio
async def test_translatable_field_constraints(async_client: AsyncClient, auth_headers: dict) -> None:
    ok = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "object",
            "name": "test_translatable_field",
            "label": {"de": "Beschreibung"},
            "field_type": "text",
            "is_repeatable": False,
            "is_translatable": True,
            "settings": {},
        },
    )
    assert ok.status_code == 201, ok.text
    field_id = ok.json()["id"]

    try:
        repeatable = await async_client.post(
            "/v1/schema",
            headers=auth_headers,
            json={
                "target_type": "object",
                "name": "test_translatable_repeatable",
                "label": {"de": "Titel"},
                "field_type": "text",
                "is_repeatable": True,
                "is_translatable": True,
                "settings": {},
            },
        )
        assert repeatable.status_code == 422, repeatable.text

        number = await async_client.post(
            "/v1/schema",
            headers=auth_headers,
            json={
                "target_type": "object",
                "name": "test_translatable_number",
                "label": {"de": "Anzahl"},
                "field_type": "number",
                "is_translatable": True,
                "settings": {},
            },
        )
        assert number.status_code == 422, number.text
    finally:
        await async_client.delete(f"/v1/schema/{field_id}", headers=auth_headers)


@pytest.mark.asyncio
async def test_recreate_soft_deleted_field_reactivates_same_id(
    async_client: AsyncClient, auth_headers: dict
) -> None:
    payload = {
        "target_type": "object",
        "name": "reactivate_test_field",
        "label": {"de": "Reaktivierung"},
        "field_type": "text",
        "is_required": False,
        "is_repeatable": False,
        "is_translatable": False,
        "sort_order": 98,
        "settings": {},
    }
    created = await async_client.post("/v1/schema", headers=auth_headers, json=payload)
    assert created.status_code == 201, created.text
    field_id = created.json()["id"]

    deleted = await async_client.delete(f"/v1/schema/{field_id}", headers=auth_headers)
    assert deleted.status_code == 204

    recreated = await async_client.post("/v1/schema", headers=auth_headers, json=payload)
    assert recreated.status_code == 201, recreated.text
    data = recreated.json()
    assert data["id"] == field_id
    assert data["name"] == payload["name"]

    await async_client.delete(f"/v1/schema/{field_id}", headers=auth_headers)
