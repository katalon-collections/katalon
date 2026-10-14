# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid

import pytest


async def _post_field(async_client, auth_headers, **body) -> str:
    response = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={"target_type": "object", "label": {"de": body["name"]}, **body},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


@pytest.mark.asyncio
async def test_usage_summary_matches_per_field_usage(async_client, auth_headers) -> None:
    p = f"us_{uuid.uuid4().hex[:6]}"
    text_id = await _post_field(async_client, auth_headers, name=f"{p}_text", field_type="text")
    group_id = await _post_field(
        async_client, auth_headers, name=f"{p}_grp", field_type="group", is_repeatable=True
    )
    sub_id = await _post_field(
        async_client, auth_headers, name=f"{p}_sub", field_type="text", parent_id=group_id
    )

    metadatas = [
        {"label": "a", f"{p}_text": "x", f"{p}_grp": [{f"{p}_sub": "y"}]},
        {"label": "b", f"{p}_text": "", f"{p}_grp": [{f"{p}_sub": ""}, {f"{p}_sub": "z"}]},
        {"label": "c", f"{p}_grp": [{f"{p}_sub": ""}]},
    ]
    for metadata in metadatas:
        response = await async_client.post(
            "/v1/objects",
            headers=auth_headers,
            json={"idno": f"US-{uuid.uuid4().hex[:10]}", "status": "draft", "metadata_": metadata},
        )
        assert response.status_code == 201, response.text

    summary = await async_client.get("/v1/schema/object/usage-summary", headers=auth_headers)
    assert summary.status_code == 200, summary.text
    by_id = {item["field_id"]: item for item in summary.json()}

    for field_id in (text_id, group_id, sub_id):
        single = await async_client.get(f"/v1/schema/{field_id}/usage", headers=auth_headers)
        assert by_id[field_id]["usage_count"] == single.json()["usage_count"]
    assert by_id[text_id]["usage_count"] == 1
    assert by_id[sub_id]["usage_count"] == 2
    assert by_id[sub_id]["parent_id"] == group_id


@pytest.mark.asyncio
async def test_usage_summary_rejects_unknown_type(async_client, auth_headers) -> None:
    response = await async_client.get("/v1/schema/nope/usage-summary", headers=auth_headers)
    assert response.status_code == 422
