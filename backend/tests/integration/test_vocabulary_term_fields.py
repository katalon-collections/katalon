import json
import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_vocabulary_term_schema_and_metadata_validation(
    async_client: AsyncClient, auth_headers: dict
) -> None:
    name = f"term-fields-{uuid.uuid4()}"
    vocab_response = await async_client.post(
        "/v1/vocabularies",
        headers=auth_headers,
        json={"name": name, "is_hierarchical": False, "kind": "term"},
    )
    assert vocab_response.status_code == 201, vocab_response.text
    vocab = vocab_response.json()
    assert vocab["kind"] == "term"

    field_response = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "vocabulary_term",
            "target_subtype": vocab["id"],
            "name": "note",
            "label": {"de": "Bemerkung"},
            "field_type": "text",
            "is_required": True,
            "settings": {},
        },
    )
    assert field_response.status_code == 201, field_response.text

    invalid = await async_client.post(
        f"/v1/vocabularies/{vocab['id']}/terms",
        headers=auth_headers,
        json={
            "vocabulary_id": vocab["id"],
            "term": "diskette",
            "label": {"de": "Diskette"},
            "metadata_": {},
        },
    )
    assert invalid.status_code == 422

    valid = await async_client.post(
        f"/v1/vocabularies/{vocab['id']}/terms",
        headers=auth_headers,
        json={
            "vocabulary_id": vocab["id"],
            "term": "diskette",
            "label": {"de": "Diskette"},
            "metadata_": {"note": "3,5 Zoll"},
        },
    )
    assert valid.status_code == 201, valid.text
    assert valid.json()["metadata_"]["note"] == "3,5 Zoll"


@pytest.mark.asyncio
async def test_vocabulary_kind_limits_schema_usage(
    async_client: AsyncClient, auth_headers: dict
) -> None:
    listed = await async_client.get("/v1/vocabularies", headers=auth_headers)
    relation_types = next(v for v in listed.json() if v["name"] == "relation_types")
    assert relation_types["kind"] == "relation"

    relation_response = await async_client.post(
        "/v1/vocabularies",
        headers=auth_headers,
        json={
            "name": f"relations-{uuid.uuid4()}",
            "is_hierarchical": False,
            "kind": "relation",
        },
    )
    relation_vocab = relation_response.json()

    term_response = await async_client.post(
        f"/v1/vocabularies/{relation_vocab['id']}/terms",
        headers=auth_headers,
        json={
            "vocabulary_id": relation_vocab["id"],
            "term": "has_author",
            "label": {"de": "hat Autor"},
            "applies_from": ["object"],
            "applies_to": ["entity"],
        },
    )
    assert term_response.status_code == 201, term_response.text

    invalid = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "object",
            "name": f"invalid_vocab_{uuid.uuid4().hex}",
            "label": {"de": "Falsch"},
            "field_type": "vocab",
            "settings": {"vocabulary_id": relation_vocab["id"]},
        },
    )
    assert invalid.status_code == 422

    valid = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "object",
            "name": f"relation_{uuid.uuid4().hex}",
            "label": {"de": "Relation"},
            "field_type": "relation",
            "settings": {
                "target_type": "entity",
                "relation_type_vocab": relation_vocab["id"],
            },
        },
    )
    assert valid.status_code == 201, valid.text


@pytest.mark.asyncio
async def test_relation_vocabulary_rejects_hierarchy(
    async_client: AsyncClient, auth_headers: dict
) -> None:
    response = await async_client.post(
        "/v1/vocabularies",
        headers=auth_headers,
        json={
            "name": f"flat-relations-{uuid.uuid4()}",
            "is_hierarchical": True,
            "kind": "relation",
        },
    )
    assert response.status_code == 201, response.text
    vocab = response.json()
    assert vocab["is_hierarchical"] is False

    parent = await async_client.post(
        f"/v1/vocabularies/{vocab['id']}/terms",
        headers=auth_headers,
        json={
            "vocabulary_id": vocab["id"],
            "term": "has_author",
            "label": {"de": "hat Autor"},
        },
    )
    assert parent.status_code == 201, parent.text

    child = await async_client.post(
        f"/v1/vocabularies/{vocab['id']}/terms",
        headers=auth_headers,
        json={
            "vocabulary_id": vocab["id"],
            "term": "has_creator",
            "label": {"de": "hat Urheber"},
            "parent_id": parent.json()["id"],
        },
    )
    assert child.status_code == 422

    updated = await async_client.put(
        f"/v1/vocabularies/terms/{parent.json()['id']}",
        headers=auth_headers,
        json={
            "vocabulary_id": vocab["id"],
            "term": "has_author",
            "label": {"de": "hat Autor"},
            "parent_id": parent.json()["id"],
        },
    )
    assert updated.status_code == 422

    imported = await async_client.post(
        f"/v1/vocabularies/{vocab['id']}/import?dry_run=true",
        headers=auth_headers,
        data={"mapping": json.dumps({"term": "term", "parent": "parent_term"})},
        files={"file": ("relation-types.csv", b"term;parent\nhas_editor;has_author\n", "text/csv")},
    )
    assert imported.status_code == 422
