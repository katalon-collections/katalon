# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Export context: inbound cap for the index copy, deleted/non-public targets."""

import uuid

import pytest
from sqlalchemy import text


async def _create(async_client, auth_headers, path: str, label: str, status: str = "public") -> str:
    response = await async_client.post(
        f"/v1/{path}",
        headers=auth_headers,
        json={
            "idno": f"EC-{uuid.uuid4().hex[:10]}",
            "status": status,
            "metadata_": {"label": label},
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def _relate(async_client, auth_headers, from_type, from_id, to_type, to_id, rtype) -> None:
    response = await async_client.post(
        "/v1/relations",
        headers=auth_headers,
        json={
            "from_type": from_type,
            "from_id": from_id,
            "to_type": to_type,
            "to_id": to_id,
            "relation_type": rtype,
            "metadata_": {},
        },
    )
    assert response.status_code == 201, response.text


@pytest.mark.asyncio
async def test_index_copy_omits_large_inbound_and_exports_expand_it(
    async_client, auth_headers
) -> None:
    import katalon.database as database_module
    from katalon.services import export_context_service as ecs

    collection_id = await _create(async_client, auth_headers, "collections", "Große Sammlung")
    for i in range(5):
        object_id = await _create(async_client, auth_headers, "objects", f"Karte {i}")
        await _relate(
            async_client, auth_headers, "object", object_id, "collection", collection_id, "part_of"
        )

    async with database_module.AsyncSessionLocal() as db:
        capped = await ecs.build_export_context_from_db(
            db, "collection", uuid.UUID(collection_id), max_inbound=3
        )
        full = await ecs.build_export_context_from_db(db, "collection", uuid.UUID(collection_id))
        under_cap = await ecs.build_export_context_from_db(
            db, "collection", uuid.UUID(collection_id), max_inbound=10
        )

        assert capped.inbound_relations_omitted == 5
        assert [r for r in capped.relations if r.direction == "inbound"] == []
        assert len([r for r in full.relations if r.direction == "inbound"]) == 5
        assert under_cap.inbound_relations_omitted == 0
        assert len(under_cap.relations) == 5

        hits = [{"_id": collection_id, "_source": {"export_context": capped.to_dict()}}]
        await ecs.refresh_index_contexts(db, hits)
        expanded = hits[0]["_source"]["export_context"]
        assert expanded["inbound_relations_omitted"] == 0
        assert len(expanded["relations"]) == 5


@pytest.mark.asyncio
async def test_deleted_and_non_public_targets_are_excluded(async_client, auth_headers) -> None:
    import katalon.database as database_module
    from katalon.services import export_context_service as ecs

    object_id = await _create(async_client, auth_headers, "objects", "Postkarte")
    kept = await _create(async_client, auth_headers, "entities", "Verlag", status="published")
    deleted = await _create(async_client, auth_headers, "entities", "Gelöscht")
    draft = await _create(async_client, auth_headers, "entities", "Entwurf", status="draft")
    for target in (kept, deleted, draft):
        await _relate(async_client, auth_headers, "object", object_id, "entity", target, "creator")
    # The API refuses to delete a linked entity (409); soft-delete it directly,
    # as a purge-pending record that still carries its relation would look.
    async with database_module.AsyncSessionLocal() as db:
        await db.execute(
            text("UPDATE entities SET deleted_at = now() WHERE id = :id"), {"id": uuid.UUID(deleted)}
        )
        await db.commit()

    async with database_module.AsyncSessionLocal() as db:
        ctx = await ecs.build_export_context_from_db(db, "object", uuid.UUID(object_id))
    assert {r.target_id for r in ctx.relations} == {kept}


@pytest.mark.asyncio
async def test_soft_deleted_record_cannot_be_exported(async_client, auth_headers) -> None:
    import katalon.database as database_module
    from katalon.services import export_context_service as ecs

    object_id = await _create(async_client, auth_headers, "objects", "Gelöschte Karte")
    response = await async_client.delete(f"/v1/objects/{object_id}", headers=auth_headers)
    assert response.status_code == 204

    async with database_module.AsyncSessionLocal() as db:
        with pytest.raises(ValueError):
            await ecs.build_export_context_from_db(db, "object", uuid.UUID(object_id))
