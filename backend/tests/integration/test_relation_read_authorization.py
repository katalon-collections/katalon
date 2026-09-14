# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Issue #388: `/v1/relations` must require authentication and must not
surface a relation whose *other* endpoint the caller may not read — a viewer
can read objects but never procedures, so an object<->procedure relation must
be hidden entirely from a viewer's relation list, not just have its label
blanked out."""

import uuid

import pytest


async def _create_role_user(async_client, auth_headers: dict[str, str], role: str) -> dict[str, str]:
    email = f"{role}-{uuid.uuid4().hex[:10]}@katalon.dev"
    password = "Test1234"
    created = await async_client.post(
        "/v1/users", headers=auth_headers, json={"email": email, "password": password, "role": role},
    )
    assert created.status_code == 201, created.text
    token = (
        await async_client.post(
            "/v1/auth/token", data={"username": email, "password": password},
        )
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _setup_object_procedure_relation(async_client, auth_headers):
    object_res = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={"idno": f"OBJ-{uuid.uuid4().hex[:12]}", "status": "draft", "metadata_": {"label": "Kiste"}},
    )
    assert object_res.status_code == 201, object_res.text
    object_id = object_res.json()["id"]

    procedure_res = await async_client.post(
        "/v1/procedures",
        headers=auth_headers,
        json={
            "idno": f"PRO-{uuid.uuid4().hex[:12]}",
            "procedure_type": "conservation",
            "status": "draft",
            "metadata_": {"label": "Restaurierung"},
        },
    )
    assert procedure_res.status_code == 201, procedure_res.text
    procedure_id = procedure_res.json()["id"]

    relation_res = await async_client.post(
        "/v1/relations",
        headers=auth_headers,
        json={
            "from_type": "object",
            "from_id": object_id,
            "to_type": "procedure",
            "to_id": procedure_id,
            "relation_type": "concerns",
            "metadata_": {},
        },
    )
    assert relation_res.status_code == 201, relation_res.text
    return object_id, procedure_id


@pytest.mark.asyncio
async def test_relations_require_authentication(async_client, auth_headers) -> None:
    object_id, _ = await _setup_object_procedure_relation(async_client, auth_headers)
    res = await async_client.get("/v1/relations", params={"from_type": "object", "from_id": object_id})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_viewer_never_sees_relation_to_unreadable_procedure(async_client, auth_headers) -> None:
    object_id, procedure_id = await _setup_object_procedure_relation(async_client, auth_headers)
    viewer_headers = await _create_role_user(async_client, auth_headers, "viewer")

    res = await async_client.get(
        "/v1/relations", headers=viewer_headers, params={"from_type": "object", "from_id": object_id},
    )
    assert res.status_code == 200
    relations = res.json()
    # The relation exists but its unreadable-to-viewer endpoint (procedure)
    # must not be exposed via id, type, or label — the relation is dropped
    # entirely rather than returned with a nulled-out counterpart.
    assert not any(r["to_id"] == procedure_id for r in relations)


@pytest.mark.asyncio
async def test_cataloger_sees_relation_to_readable_procedure(async_client, auth_headers) -> None:
    object_id, procedure_id = await _setup_object_procedure_relation(async_client, auth_headers)
    cataloger_headers = await _create_role_user(async_client, auth_headers, "cataloger")

    res = await async_client.get(
        "/v1/relations", headers=cataloger_headers, params={"from_type": "object", "from_id": object_id},
    )
    assert res.status_code == 200
    relations = res.json()
    matching = [r for r in relations if r["to_id"] == procedure_id]
    assert len(matching) == 1
    assert matching[0]["to_label"] == "Restaurierung"
