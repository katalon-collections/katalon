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


@pytest.mark.asyncio
async def test_referenced_term_deletion_requires_confirmation_and_can_remap_or_force(
    async_client, auth_headers
) -> None:
    create_vocab = await async_client.post(
        "/v1/vocabularies",
        headers=auth_headers,
        json={"name": f"Term deletion {uuid.uuid4().hex[:8]}"},
    )
    assert create_vocab.status_code == 201, create_vocab.text
    vocab_id = create_vocab.json()["id"]

    field_name = f"term_reference_{uuid.uuid4().hex[:8]}"
    create_field = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "object",
            "name": field_name,
            "label": {"de": "Termreferenz"},
            "field_type": "vocab",
            "settings": {"vocabulary_id": vocab_id},
        },
    )
    assert create_field.status_code == 201, create_field.text

    async def create_term(term: str, label: str) -> dict:
        response = await async_client.post(
            f"/v1/vocabularies/{vocab_id}/terms",
            headers=auth_headers,
            json={"vocabulary_id": vocab_id, "term": term, "label": {"de": label}},
        )
        assert response.status_code == 201, response.text
        return response.json()

    source = await create_term("source", "Quellterm")
    replacement = await create_term("replacement", "Ersatzterm")
    force_only = await create_term("force-only", "Nur erzwungen")

    async def create_object(term: dict, prefix: str) -> dict:
        response = await async_client.post(
            "/v1/objects",
            headers=auth_headers,
            json={
                "idno": f"{prefix}-{uuid.uuid4().hex[:12]}",
                "metadata_": {
                    "label": f"Objekt für {prefix}",
                    field_name: {"id": term["id"], "label": term["label"]["de"]},
                },
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    remapped_object = await create_object(source, "TERM-REMAP")
    force_deleted_object = await create_object(force_only, "TERM-FORCE")

    guarded = await async_client.delete(
        f"/v1/vocabularies/terms/{source['id']}", headers=auth_headers
    )
    assert guarded.status_code == 409, guarded.text
    assert guarded.json()["detail"] == {
        "error": "term_in_use",
        "related_count": 1,
        "message": "1 Datensätze verweisen auf diesen Term.",
    }

    remapped = await async_client.delete(
        f"/v1/vocabularies/terms/{source['id']}",
        headers=auth_headers,
        params={"replacement_term_id": replacement["id"]},
    )
    assert remapped.status_code == 204, remapped.text
    remapped_record = await async_client.get(
        f"/v1/objects/{remapped_object['id']}", headers=auth_headers
    )
    assert remapped_record.status_code == 200, remapped_record.text
    assert remapped_record.json()["metadata_"][field_name] == {
        "id": replacement["id"],
        "label": "Ersatzterm",
    }

    forced = await async_client.delete(
        f"/v1/vocabularies/terms/{force_only['id']}",
        headers=auth_headers,
        params={"force": "true"},
    )
    assert forced.status_code == 204, forced.text
    force_deleted_record = await async_client.get(
        f"/v1/objects/{force_deleted_object['id']}", headers=auth_headers
    )
    assert force_deleted_record.status_code == 200, force_deleted_record.text
    assert force_deleted_record.json()["metadata_"][field_name] == {
        "id": force_only["id"],
        "label": "Nur erzwungen",
    }

    # An object that retains a force-deleted term can still be updated
    # without 422 metadata validation errors.
    update_response = await async_client.put(
        f"/v1/objects/{force_deleted_object['id']}",
        headers={**auth_headers, "If-Match": str(force_deleted_record.json()["version"])},
        json={
            "idno": force_deleted_record.json()["idno"],
            "metadata_": {
                **force_deleted_record.json()["metadata_"],
                "label": "Aktualisierter Titel nach Term-Löschung",
            },
        },
    )
    assert update_response.status_code == 200, update_response.text
    assert (
        update_response.json()["metadata_"]["label"]
        == "Aktualisierter Titel nach Term-Löschung"
    )
    assert update_response.json()["metadata_"][field_name] == {
        "id": force_only["id"],
        "label": "Nur erzwungen",
    }

    # Test remove_from_records
    remove_only = await create_term("remove-only", "Zu entfernen")
    remove_deleted_object = await create_object(remove_only, "TERM-REMOVE")

    removed = await async_client.delete(
        f"/v1/vocabularies/terms/{remove_only['id']}",
        headers=auth_headers,
        params={"remove_from_records": "true"},
    )
    assert removed.status_code == 204, removed.text
    cleaned_record = await async_client.get(
        f"/v1/objects/{remove_deleted_object['id']}", headers=auth_headers
    )
    assert cleaned_record.status_code == 200, cleaned_record.text
    assert field_name not in cleaned_record.json()["metadata_"]


@pytest.mark.asyncio
async def test_get_field_usage_counts_active_records(async_client, auth_headers) -> None:
    field_name = f"usage_test_{uuid.uuid4().hex[:8]}"
    create_field = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "object",
            "name": field_name,
            "label": {"de": "Nutzungstest"},
            "field_type": "text",
        },
    )
    assert create_field.status_code == 201, create_field.text
    field_id = create_field.json()["id"]

    # Initially 0
    usage_init = await async_client.get(f"/v1/schema/{field_id}/usage", headers=auth_headers)
    assert usage_init.status_code == 200
    assert usage_init.json()["usage_count"] == 0

    # Create 2 objects with values
    for i in range(2):
        res = await async_client.post(
            "/v1/objects",
            headers=auth_headers,
            json={
                "idno": f"USAGE-OBJ-{i}-{uuid.uuid4().hex[:8]}",
                "metadata_": {"label": f"Objekt {i}", field_name: f"Wert {i}"},
            },
        )
        assert res.status_code == 201

    usage_after = await async_client.get(f"/v1/schema/{field_id}/usage", headers=auth_headers)
    assert usage_after.status_code == 200
    assert usage_after.json()["usage_count"] == 2


@pytest.mark.asyncio
async def test_deleting_field_with_purge_data_removes_existing_record_metadata(
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
            "idno": f"SCHEMA-PURGE-{uuid.uuid4().hex[:12]}",
            "metadata_": {"label": "Objekt mit Testfeld", field_name: "zu löschender Wert"},
        },
    )
    assert created_object.status_code == 201, created_object.text
    object_id = created_object.json()["id"]

    delete_field = await async_client.delete(
        f"/v1/schema/{field_id}?purge_data=true", headers=auth_headers
    )
    assert delete_field.status_code == 204

    active_fields = await async_client.get("/v1/schema/object", headers=auth_headers)
    assert field_name not in {f["name"] for f in active_fields.json()}

    persisted = await async_client.get(f"/v1/objects/{object_id}", headers=auth_headers)
    assert persisted.status_code == 200
    assert field_name not in persisted.json()["metadata_"]


@pytest.mark.asyncio
async def test_deleting_subfield_with_purge_data_removes_nested_values(
    async_client, auth_headers
) -> None:
    group_name = f"group_{uuid.uuid4().hex[:8]}"
    create_group = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "object",
            "name": group_name,
            "label": {"de": "Gruppe", "en": "Group"},
            "field_type": "group",
        },
    )
    assert create_group.status_code == 201, create_group.text
    group_id = create_group.json()["id"]

    subfield_name = f"sub_{uuid.uuid4().hex[:8]}"
    create_sub = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "object",
            "name": subfield_name,
            "label": {"de": "Unterfeld", "en": "Subfield"},
            "field_type": "text",
            "parent_id": group_id,
        },
    )
    assert create_sub.status_code == 201, create_sub.text
    sub_id = create_sub.json()["id"]

    created_object = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"SCHEMA-SUB-PURGE-{uuid.uuid4().hex[:12]}",
            "metadata_": {
                "label": "Objekt mit Gruppe",
                group_name: [{"other": "bleibt", subfield_name: "verschwindet"}],
            },
        },
    )
    assert created_object.status_code == 201, created_object.text
    object_id = created_object.json()["id"]

    delete_sub = await async_client.delete(
        f"/v1/schema/{sub_id}?purge_data=true", headers=auth_headers
    )
    assert delete_sub.status_code == 204

    persisted = await async_client.get(f"/v1/objects/{object_id}", headers=auth_headers)
    assert persisted.status_code == 200
    group_val = persisted.json()["metadata_"][group_name]
    assert group_val == [{"other": "bleibt"}]

