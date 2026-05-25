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
