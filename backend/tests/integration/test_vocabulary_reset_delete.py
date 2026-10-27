# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid

import pytest
from httpx import AsyncClient


async def _create_vocab_with_terms(client: AsyncClient, headers: dict) -> dict:
    vocab = (
        await client.post(
            "/v1/vocabularies",
            headers=headers,
            json={"name": f"reset-{uuid.uuid4()}", "is_hierarchical": True, "kind": "term"},
        )
    ).json()
    parent = await client.post(
        f"/v1/vocabularies/{vocab['id']}/terms",
        headers=headers,
        json={"vocabulary_id": vocab["id"], "term": "parent", "label": {"de": "Eltern"}},
    )
    assert parent.status_code == 201, parent.text
    child = await client.post(
        f"/v1/vocabularies/{vocab['id']}/terms",
        headers=headers,
        json={
            "vocabulary_id": vocab["id"],
            "term": "child",
            "label": {"de": "Kind"},
            "parent_id": parent.json()["id"],
        },
    )
    assert child.status_code == 201, child.text
    return vocab


@pytest.mark.asyncio
async def test_clear_terms_keeps_vocabulary(async_client: AsyncClient, auth_headers: dict) -> None:
    vocab = await _create_vocab_with_terms(async_client, auth_headers)

    summary = await async_client.get(
        f"/v1/vocabularies/{vocab['id']}/reset-summary", headers=auth_headers
    )
    assert summary.status_code == 200, summary.text
    assert summary.json() == {"term_count": 2, "referencing_fields": 0, "is_system": False}

    cleared = await async_client.delete(
        f"/v1/vocabularies/{vocab['id']}/terms", headers=auth_headers
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["deleted_terms"] == 2
    assert cleared.json()["deleted_vocabulary"] is False

    still_there = await async_client.get(f"/v1/vocabularies/{vocab['id']}", headers=auth_headers)
    assert still_there.status_code == 200
    terms = await async_client.get(f"/v1/vocabularies/{vocab['id']}/terms", headers=auth_headers)
    assert terms.json() == []


@pytest.mark.asyncio
async def test_delete_vocabulary_removes_vocab_and_terms(
    async_client: AsyncClient, auth_headers: dict
) -> None:
    vocab = await _create_vocab_with_terms(async_client, auth_headers)

    deleted = await async_client.delete(f"/v1/vocabularies/{vocab['id']}", headers=auth_headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"deleted_terms": 2, "deleted_vocabulary": True, "deactivated_fields": 0}

    missing = await async_client.get(f"/v1/vocabularies/{vocab['id']}", headers=auth_headers)
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_delete_vocabulary_referenced_by_schema_field_requires_force(
    async_client: AsyncClient, auth_headers: dict
) -> None:
    vocab = await _create_vocab_with_terms(async_client, auth_headers)
    field = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "object",
            "name": f"vocab_ref_{uuid.uuid4().hex[:8]}",
            "label": {"de": "Vokabularfeld"},
            "field_type": "vocab",
            "settings": {"vocabulary_id": vocab["id"]},
        },
    )
    assert field.status_code == 201, field.text

    blocked = await async_client.delete(f"/v1/vocabularies/{vocab['id']}", headers=auth_headers)
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["related_count"] == 1

    forced = await async_client.delete(
        f"/v1/vocabularies/{vocab['id']}?force=true", headers=auth_headers
    )
    assert forced.status_code == 200, forced.text
    assert forced.json()["deactivated_fields"] == 1

    fields = await async_client.get("/v1/schema/object", headers=auth_headers)
    assert field.json()["id"] not in {f["id"] for f in fields.json()}


@pytest.mark.asyncio
async def test_system_vocabulary_cannot_be_deleted_but_can_be_cleared_summary(
    async_client: AsyncClient, auth_headers: dict
) -> None:
    vocabs = (await async_client.get("/v1/vocabularies", headers=auth_headers)).json()
    media = next((v for v in vocabs if v["name"] == "media_types"), None)
    if media is None:
        pytest.skip("media_types vocabulary not seeded in this test setup")

    summary = await async_client.get(
        f"/v1/vocabularies/{media['id']}/reset-summary", headers=auth_headers
    )
    assert summary.json()["is_system"] is True

    blocked = await async_client.delete(
        f"/v1/vocabularies/{media['id']}?force=true", headers=auth_headers
    )
    assert blocked.status_code == 409
