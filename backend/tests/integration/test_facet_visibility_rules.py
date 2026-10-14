# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid

import pytest


async def _create(async_client, auth_headers, **flags):
    response = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "object",
            "name": f"fv_{uuid.uuid4().hex[:8]}",
            "label": {"de": "Feld"},
            "field_type": "text",
            **flags,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_facet_without_detail_display_is_allowed(async_client, auth_headers) -> None:
    field = await _create(
        async_client, auth_headers, is_facet=True, show_in_detail=False, is_public=True
    )
    assert field["is_facet"] is True
    assert field["show_in_detail"] is False


@pytest.mark.asyncio
async def test_non_public_field_cannot_be_facet(async_client, auth_headers) -> None:
    field = await _create(async_client, auth_headers, is_facet=True, is_public=False)
    assert field["is_facet"] is False

    public = await _create(async_client, auth_headers, is_facet=True, is_public=True)
    body = {k: v for k, v in public.items() if k not in ("id", "children")}
    body["is_public"] = False
    response = await async_client.put(f"/v1/schema/{public['id']}", headers=auth_headers, json=body)
    assert response.status_code == 200, response.text
    assert response.json()["is_facet"] is False
