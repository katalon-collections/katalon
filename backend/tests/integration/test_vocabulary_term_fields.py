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
async def test_new_term_is_immediately_available_in_its_vocabulary(
    async_client: AsyncClient, auth_headers: dict
) -> None:
    vocab_response = await async_client.post(
        "/v1/vocabularies",
        headers=auth_headers,
        json={"name": f"immediate-terms-{uuid.uuid4()}", "is_hierarchical": False, "kind": "term"},
    )
    vocab = vocab_response.json()

    created = await async_client.post(
        f"/v1/vocabularies/{vocab['id']}/terms",
        headers=auth_headers,
        json={
            "vocabulary_id": vocab["id"],
            "term": "new-term",
            "label": {"de": "Neuer Term"},
        },
    )
    assert created.status_code == 201, created.text

    listed = await async_client.get(f"/v1/vocabularies/{vocab['id']}/terms", headers=auth_headers)
    assert "new-term" in {term["term"] for term in listed.json()}


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


@pytest.mark.asyncio
async def test_hierarchical_terms_reject_cycles_and_promote_children_on_delete(
    async_client: AsyncClient, auth_headers: dict
) -> None:
    vocab_response = await async_client.post(
        "/v1/vocabularies",
        headers=auth_headers,
        json={"name": f"hierarchy-{uuid.uuid4()}", "is_hierarchical": True, "kind": "term"},
    )
    assert vocab_response.status_code == 201, vocab_response.text
    vocab = vocab_response.json()

    async def create(term: str, parent_id: str | None = None) -> dict:
        response = await async_client.post(
            f"/v1/vocabularies/{vocab['id']}/terms",
            headers=auth_headers,
            json={
                "vocabulary_id": vocab["id"],
                "term": term,
                "label": {"de": term},
                "parent_id": parent_id,
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    root = await create("root")
    child = await create("child", root["id"])
    grandchild = await create("grandchild", child["id"])

    other_vocab = await async_client.post(
        "/v1/vocabularies",
        headers=auth_headers,
        json={"name": f"other-{uuid.uuid4()}", "is_hierarchical": True, "kind": "term"},
    )
    assert other_vocab.status_code == 201, other_vocab.text
    foreign_parent = await async_client.post(
        f"/v1/vocabularies/{other_vocab.json()['id']}/terms",
        headers=auth_headers,
        json={
            "vocabulary_id": other_vocab.json()["id"],
            "term": "foreign",
            "label": {"de": "foreign"},
        },
    )
    assert foreign_parent.status_code == 201, foreign_parent.text
    foreign_parent_link = await async_client.post(
        f"/v1/vocabularies/{vocab['id']}/terms",
        headers=auth_headers,
        json={
            "vocabulary_id": vocab["id"],
            "term": "wrong-parent",
            "label": {"de": "wrong-parent"},
            "parent_id": foreign_parent.json()["id"],
        },
    )
    assert foreign_parent_link.status_code == 422

    cycle = await async_client.put(
        f"/v1/vocabularies/terms/{root['id']}",
        headers=auth_headers,
        json={
            "vocabulary_id": vocab["id"],
            "term": "root",
            "label": {"de": "root"},
            "parent_id": grandchild["id"],
        },
    )
    assert cycle.status_code == 422

    deleted = await async_client.delete(
        f"/v1/vocabularies/terms/{root['id']}", headers=auth_headers
    )
    assert deleted.status_code == 204, deleted.text
    child_after_delete = await async_client.get(
        f"/v1/vocabularies/{vocab['id']}/terms/{child['id']}", headers=auth_headers
    )
    assert child_after_delete.status_code == 200, child_after_delete.text
    assert child_after_delete.json()["parent_id"] is None
