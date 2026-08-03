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
        json={"target_type": "entity", "name": "Voll", "field_names": []},
    )
    variant_id = create_r.json()["id"]

    update_r = await async_client.put(
        f"/v1/form-variants/{variant_id}",
        headers=auth_headers,
        json={"target_type": "entity", "name": "Vollerfassung", "field_names": [], "sort_order": 5},
    )
    assert update_r.status_code == 200, update_r.text
    assert update_r.json()["name"] == "Vollerfassung"
    assert update_r.json()["sort_order"] == 5


@pytest.mark.asyncio
async def test_delete_form_variant_soft_deletes(async_client: AsyncClient, auth_headers: dict) -> None:
    create_r = await async_client.post(
        "/v1/form-variants",
        headers=auth_headers,
        json={"target_type": "place", "name": "Temp", "field_names": []},
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
        json={"target_type": "occurrence", "name": "Kurationsmaske", "field_names": []},
    )
    variant_id = create_r.json()["id"]

    set_r = await async_client.post(
        f"/v1/form-variants/{variant_id}/role-defaults/admin",
        headers=auth_headers,
    )
    assert set_r.status_code == 204

    # auth_headers logs in as the admin user, so its own role-default now shows up.
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
        json={"target_type": "procedure", "name": "A", "field_names": []},
    )
    second_r = await async_client.post(
        "/v1/form-variants",
        headers=auth_headers,
        json={"target_type": "procedure", "name": "B", "field_names": []},
    )
    first_id, second_id = first_r.json()["id"], second_r.json()["id"]

    await async_client.post(f"/v1/form-variants/{first_id}/role-defaults/editor", headers=auth_headers)
    await async_client.post(f"/v1/form-variants/{second_id}/role-defaults/editor", headers=auth_headers)

    list_r = await async_client.get("/v1/form-variants?target_type=procedure", headers=auth_headers)
    by_id = {v["id"]: v for v in list_r.json()}
    # Only the second variant should still claim the "editor" default — but the
    # requesting user is admin, so role-default visibility is scoped to *their*
    # role and won't show "editor" here. Assert via direct role-default removal
    # instead, which 404s once the first claim was already superseded.
    remove_stale_r = await async_client.delete(
        f"/v1/form-variants/{first_id}/role-defaults/editor", headers=auth_headers
    )
    assert remove_stale_r.status_code == 404
    remove_current_r = await async_client.delete(
        f"/v1/form-variants/{second_id}/role-defaults/editor", headers=auth_headers
    )
    assert remove_current_r.status_code == 204
    assert by_id  # keep list_r result referenced/used
