# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid

import pytest


async def _create(client, headers, path: str, label: str, status: str = "public") -> str:
    response = await client.post(
        f"/v1/{path}",
        headers=headers,
        json={"idno": f"LG-{uuid.uuid4().hex[:8]}", "status": status, "metadata_": {"label": label}},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def _member(client, headers, object_id: str, collection_id: str) -> None:
    response = await client.post(
        "/v1/relations",
        headers=headers,
        json={
            "from_type": "object",
            "from_id": object_id,
            "to_type": "collection",
            "to_id": collection_id,
            "relation_type": "member_of",
            "metadata_": {},
        },
    )
    assert response.status_code == 201, response.text


@pytest.mark.asyncio
async def test_largest_orders_by_public_members(async_client, auth_headers) -> None:
    p = uuid.uuid4().hex[:6]
    small = await _create(async_client, auth_headers, "collections", f"klein {p}")
    big = await _create(async_client, auth_headers, "collections", f"groß {p}")
    drafts = await _create(async_client, auth_headers, "collections", f"entwürfe {p}")
    for _ in range(3):
        await _member(async_client, auth_headers, await _create(async_client, auth_headers, "objects", "o"), big)
    await _member(async_client, auth_headers, await _create(async_client, auth_headers, "objects", "o"), small)
    for _ in range(5):  # draft members do not count
        await _member(
            async_client, auth_headers,
            await _create(async_client, auth_headers, "objects", "o", status="draft"), drafts,
        )

    response = await async_client.get(
        "/portal/v1/collections", params={"sort": "largest", "q": p, "page_size": 10}
    )
    assert response.status_code == 200, response.text
    ids = [item["id"] for item in response.json()["items"]]
    assert ids.index(big) < ids.index(small) < ids.index(drafts)

    assert (await async_client.get("/portal/v1/collections", params={"sort": "biggest"})).status_code == 422
