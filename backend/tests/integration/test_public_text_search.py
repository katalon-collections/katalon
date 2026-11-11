# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Free-text search for callers without read permission only matches public fields."""

import uuid

import pytest


@pytest.mark.asyncio
async def test_portal_collection_search_ignores_internal_fields(async_client, auth_headers) -> None:
    import katalon.database as database_module
    from katalon.core.models import FieldDefinition

    marker = uuid.uuid4().hex[:8]
    internal = f"intern_{marker}"
    group = f"gruppe_{marker}"
    public_sub = f"oeffentlich_{marker}"
    internal_sub = f"geheim_{marker}"
    async with database_module.AsyncSessionLocal() as session:
        group_def = FieldDefinition(
            id=uuid.uuid4(),
            target_type="collection",
            name=group,
            label={"de": "Gruppe"},
            field_type="group",
            is_repeatable=True,
            is_public=True,
        )
        session.add_all(
            (
                FieldDefinition(
                    target_type="collection",
                    name=internal,
                    label={"de": "Intern"},
                    field_type="text",
                    is_public=False,
                ),
                group_def,
                FieldDefinition(
                    target_type="collection",
                    name=public_sub,
                    label={"de": "Öffentlich"},
                    field_type="text",
                    parent_id=group_def.id,
                    is_public=True,
                ),
                FieldDefinition(
                    target_type="collection",
                    name=internal_sub,
                    label={"de": "Geheim"},
                    field_type="text",
                    parent_id=group_def.id,
                    is_public=False,
                ),
            )
        )
        await session.commit()

    response = await async_client.post(
        "/v1/collections",
        headers=auth_headers,
        json={
            "idno": f"TS-{marker}",
            "status": "public",
            "metadata_": {
                "label": f"Sammlung {marker}",
                internal: f"spender{marker}",
                group: [{public_sub: f"sichtbar{marker}", internal_sub: f"tresor{marker}"}],
            },
        },
    )
    assert response.status_code == 201, response.text
    collection_id = response.json()["id"]

    async def anonymous_hits(q: str) -> list[str]:
        r = await async_client.get("/portal/v1/collections", params={"q": q, "page_size": 50})
        assert r.status_code == 200, r.text
        return [item["id"] for item in r.json()["items"]]

    assert collection_id in await anonymous_hits(f"sichtbar{marker}")
    assert collection_id not in await anonymous_hits(f"spender{marker}")
    assert collection_id not in await anonymous_hits(f"tresor{marker}")

    # Staff with read permission still finds internal text.
    r = await async_client.get(
        "/v1/collections", headers=auth_headers, params={"q": f"tresor{marker}"}
    )
    assert collection_id in [item["id"] for item in r.json()["items"]]
