"""Integration tests for form variants (#275): named field-selection/order
variants per record type/subtype, with role-based defaults."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_form_variants_requires_target_type(async_client: AsyncClient, auth_headers: dict) -> None:
    r = await async_client.get("/v1/form-variants", headers=auth_headers)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_list_form_variants_rejects_unknown_target_type(async_client: AsyncClient, auth_headers: dict) -> None:
    r = await async_client.get("/v1/form-variants?target_type=nonsense", headers=auth_headers)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_list_form_variants_empty_by_default(async_client: AsyncClient, auth_headers: dict) -> None:
    r = await async_client.get("/v1/form-variants?target_type=entity", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_create_form_variant_requires_admin(async_client: AsyncClient) -> None:
    r = await async_client.post(
        "/v1/form-variants",
        json={"target_type": "object", "name": "Schnellerfassung", "field_names": []},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_create_form_variant_rejects_unknown_field_names(async_client: AsyncClient, auth_headers: dict) -> None:
    r = await async_client.post(
        "/v1/form-variants",
        headers=auth_headers,
        json={
            "target_type": "object",
            "name": "Schnellerfassung",
            "field_names": ["definitely_not_a_real_field"],
        },
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_form_variant_rejects_missing_required_field(async_client: AsyncClient, auth_headers: dict) -> None:
    # "label" is required for every primary type (system field); a variant
    # that omits it must be rejected so a required field can never be hidden.
    r = await async_client.post(
        "/v1/form-variants",
        headers=auth_headers,
        json={"target_type": "entity", "name": "Ohne Pflichtfeld", "field_names": []},
    )
    assert r.status_code == 422
    assert "label" in r.json()["detail"]


@pytest.mark.asyncio
async def test_create_form_variant_requires_group_with_required_child(
    async_client: AsyncClient, auth_headers: dict
) -> None:
    subtype_name = "form_variant_required_child_scope"
    subtype_r = await async_client.post(
        "/v1/record-subtypes",
        headers=auth_headers,
        json={
            "primary_type": "object",
            "name": subtype_name,
            "label": {"de": "Formularvarianten-Test"},
        },
    )
    assert subtype_r.status_code == 201, subtype_r.text
    subtype_id = subtype_r.json()["id"]
    group_id = child_id = variant_id = None

    try:
        group_name = "variant_required_child_group"
        group_r = await async_client.post(
            "/v1/schema",
            headers=auth_headers,
            json={
                "target_type": "object",
                "target_subtype": subtype_name,
                "name": group_name,
                "label": {"de": "Pflicht-Unterfeld-Gruppe"},
                "field_type": "group",
                "is_required": False,
                "is_repeatable": True,
                "sort_order": 99,
                "settings": {},
            },
        )
        assert group_r.status_code == 201, group_r.text
        group_id = group_r.json()["id"]

        child_r = await async_client.post(
            "/v1/schema",
            headers=auth_headers,
            json={
                "target_type": "object",
                "target_subtype": subtype_name,
                "name": "variant_required_child",
                "label": {"de": "Pflicht-Unterfeld"},
                "field_type": "text",
                "is_required": True,
                "is_repeatable": False,
                "sort_order": 0,
                "settings": {},
                "parent_id": group_id,
            },
        )
        assert child_r.status_code == 201, child_r.text
        child_id = child_r.json()["id"]

        without_group_r = await async_client.post(
            "/v1/form-variants",
            headers=auth_headers,
            json={
                "target_type": "object",
                "target_subtype": subtype_name,
                "name": "Ohne Gruppe",
                "field_names": ["label"],
            },
        )
        assert without_group_r.status_code == 422
        assert group_name in without_group_r.json()["detail"]

        with_group_r = await async_client.post(
            "/v1/form-variants",
            headers=auth_headers,
            json={
                "target_type": "object",
                "target_subtype": subtype_name,
                "name": "Mit Gruppe",
                "field_names": ["label", group_name],
            },
        )
        assert with_group_r.status_code == 201, with_group_r.text
        variant_id = with_group_r.json()["id"]
    finally:
        cleanup_statuses = []
        if variant_id is not None:
            cleanup_statuses.append(
                (await async_client.delete(f"/v1/form-variants/{variant_id}", headers=auth_headers)).status_code
            )
        if child_id is not None:
            cleanup_statuses.append(
                (await async_client.delete(f"/v1/schema/{child_id}", headers=auth_headers)).status_code
            )
        if group_id is not None:
            cleanup_statuses.append(
                (await async_client.delete(f"/v1/schema/{group_id}", headers=auth_headers)).status_code
            )
        cleanup_statuses.append(
            (await async_client.delete(f"/v1/record-subtypes/{subtype_id}", headers=auth_headers)).status_code
        )
        assert cleanup_statuses == [204] * len(cleanup_statuses)


@pytest.mark.asyncio
async def test_create_and_list_form_variant(async_client: AsyncClient, auth_headers: dict) -> None:
    # "label" is a system field guaranteed to exist for every primary type.
    create_r = await async_client.post(
        "/v1/form-variants",
        headers=auth_headers,
        json={
            "target_type": "object",
            "name": "Schnellerfassung",
            "label": {"de": "Schnellerfassung"},
            "field_names": ["label"],
        },
    )
    assert create_r.status_code == 201, create_r.text
    variant = create_r.json()
    assert variant["field_names"] == ["label"]
    assert variant["default_for_roles"] == []

    list_r = await async_client.get("/v1/form-variants?target_type=object", headers=auth_headers)
    assert list_r.status_code == 200
    assert any(v["id"] == variant["id"] for v in list_r.json())


@pytest.mark.asyncio
async def test_update_form_variant(async_client: AsyncClient, auth_headers: dict) -> None:
    create_r = await async_client.post(
        "/v1/form-variants",
        headers=auth_headers,
        json={"target_type": "entity", "name": "Voll", "field_names": ["label"]},
    )
    variant_id = create_r.json()["id"]

    update_r = await async_client.put(
        f"/v1/form-variants/{variant_id}",
        headers=auth_headers,
        json={"target_type": "entity", "name": "Vollerfassung", "field_names": ["label"], "sort_order": 5},
    )
    assert update_r.status_code == 200, update_r.text
    assert update_r.json()["name"] == "Vollerfassung"
    assert update_r.json()["sort_order"] == 5


@pytest.mark.asyncio
async def test_delete_form_variant_soft_deletes(async_client: AsyncClient, auth_headers: dict) -> None:
    create_r = await async_client.post(
        "/v1/form-variants",
        headers=auth_headers,
        json={"target_type": "place", "name": "Temp", "field_names": ["label"]},
    )
    variant_id = create_r.json()["id"]

    delete_r = await async_client.delete(f"/v1/form-variants/{variant_id}", headers=auth_headers)
    assert delete_r.status_code == 204

    list_r = await async_client.get("/v1/form-variants?target_type=place", headers=auth_headers)
    assert all(v["id"] != variant_id for v in list_r.json())


@pytest.mark.asyncio
async def test_set_role_default_surfaces_in_list_for_that_role(async_client: AsyncClient, auth_headers: dict) -> None:
    create_r = await async_client.post(
        "/v1/form-variants",
        headers=auth_headers,
        json={"target_type": "occurrence", "name": "Kurationsmaske", "field_names": ["label"]},
    )
    variant_id = create_r.json()["id"]

    set_r = await async_client.post(
        f"/v1/form-variants/{variant_id}/role-defaults/admin",
        headers=auth_headers,
    )
    assert set_r.status_code == 204

    list_r = await async_client.get("/v1/form-variants?target_type=occurrence", headers=auth_headers)
    variant = next(v for v in list_r.json() if v["id"] == variant_id)
    assert variant["default_for_roles"] == ["admin"]

    remove_r = await async_client.delete(
        f"/v1/form-variants/{variant_id}/role-defaults/admin",
        headers=auth_headers,
    )
    assert remove_r.status_code == 204

    list_r2 = await async_client.get("/v1/form-variants?target_type=occurrence", headers=auth_headers)
    variant2 = next(v for v in list_r2.json() if v["id"] == variant_id)
    assert variant2["default_for_roles"] == []


@pytest.mark.asyncio
async def test_setting_role_default_unsets_previous_variant_for_same_role(
    async_client: AsyncClient, auth_headers: dict
) -> None:
    first_r = await async_client.post(
        "/v1/form-variants",
        headers=auth_headers,
        json={"target_type": "procedure", "name": "A", "field_names": ["label"]},
    )
    second_r = await async_client.post(
        "/v1/form-variants",
        headers=auth_headers,
        json={"target_type": "procedure", "name": "B", "field_names": ["label"]},
    )
    first_id, second_id = first_r.json()["id"], second_r.json()["id"]

    await async_client.post(f"/v1/form-variants/{first_id}/role-defaults/editor", headers=auth_headers)
    await async_client.post(f"/v1/form-variants/{second_id}/role-defaults/editor", headers=auth_headers)

    # Setting the "editor" default on the second variant must supersede the
    # first — regardless of the requesting user's own role.
    list_r = await async_client.get("/v1/form-variants?target_type=procedure", headers=auth_headers)
    by_id = {v["id"]: v for v in list_r.json()}
    assert by_id[first_id]["default_for_roles"] == []
    assert by_id[second_id]["default_for_roles"] == ["editor"]

    remove_stale_r = await async_client.delete(
        f"/v1/form-variants/{first_id}/role-defaults/editor", headers=auth_headers
    )
    assert remove_stale_r.status_code == 404
    remove_current_r = await async_client.delete(
        f"/v1/form-variants/{second_id}/role-defaults/editor", headers=auth_headers
    )
    assert remove_current_r.status_code == 204
