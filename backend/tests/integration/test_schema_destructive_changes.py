# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Destructive schema-change tests (katalon issue #382).

Deleting a field or a vocabulary term must never silently take existing
record data with it. Field deletion is a soft delete (``is_deleted``); a
vocabulary term is hard-deleted. Both are legitimate designs, but only if
existing records keep their stored values — these tests lock that contract
down so a future change cannot introduce an accidental cascade.
"""

from __future__ import annotations

import uuid

import pytest


@pytest.mark.asyncio
async def test_deleting_field_preserves_existing_record_metadata(
    async_client, auth_headers
) -> None:
    field_name = f"custom_field_{uuid.uuid4().hex[:8]}"
    create_field = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "object",
            "name": field_name,
            "label": {"de": "Testfeld", "en": "Test field"},
            "field_type": "text",
        },
    )
    assert create_field.status_code == 201, create_field.text
    field_id = create_field.json()["id"]

    created_object = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"SCHEMA-DEL-{uuid.uuid4().hex[:12]}",
            "metadata_": {"label": "Objekt mit Testfeld", field_name: "wertvoller Wert"},
        },
    )
    assert created_object.status_code == 201, created_object.text
    object_id = created_object.json()["id"]

    delete_field = await async_client.delete(f"/v1/schema/{field_id}", headers=auth_headers)
    assert delete_field.status_code == 204

    active_fields = await async_client.get("/v1/schema/object", headers=auth_headers)
    assert field_name not in {f["name"] for f in active_fields.json()}

    persisted = await async_client.get(f"/v1/objects/{object_id}", headers=auth_headers)
    assert persisted.status_code == 200
    assert persisted.json()["metadata_"][field_name] == "wertvoller Wert"


@pytest.mark.asyncio
async def test_deleting_vocabulary_term_does_not_delete_referencing_record(
    async_client, auth_headers
) -> None:
    create_vocab = await async_client.post(
        "/v1/vocabularies",
        headers=auth_headers,
        json={"name": f"Testvokabular {uuid.uuid4().hex[:8]}"},
    )
    assert create_vocab.status_code == 201, create_vocab.text
    vocab_id = create_vocab.json()["id"]

    create_term = await async_client.post(
        f"/v1/vocabularies/{vocab_id}/terms",
        headers=auth_headers,
        json={"vocabulary_id": vocab_id, "term": "Testterm", "label": {"de": "Testterm"}},
    )
    assert create_term.status_code == 201, create_term.text
    term_id = create_term.json()["id"]

    # Records reference vocab terms as a denormalized {id, label} snapshot in
    # their JSONB metadata (see import_tasks._resolve_vocab_terms), not via a
    # foreign key — this mirrors that shape without needing a full vocab
    # field definition.
    created_object = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"VOCAB-DEL-{uuid.uuid4().hex[:12]}",
            "metadata_": {
                "label": "Objekt mit Vokabularverweis",
                "referenced_term": {"id": term_id, "label": "Testterm"},
            },
        },
    )
    assert created_object.status_code == 201, created_object.text
    object_id = created_object.json()["id"]

    delete_term = await async_client.delete(
        f"/v1/vocabularies/terms/{term_id}", headers=auth_headers
    )
    assert delete_term.status_code == 204

    term_gone = await async_client.get(
        f"/v1/vocabularies/{vocab_id}/terms/{term_id}", headers=auth_headers
    )
    assert term_gone.status_code == 404

    persisted = await async_client.get(f"/v1/objects/{object_id}", headers=auth_headers)
    assert persisted.status_code == 200
    assert persisted.json()["metadata_"]["referenced_term"] == {
        "id": term_id,
        "label": "Testterm",
    }
