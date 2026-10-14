# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Facet catalog in the portal config, validation and reindex triggers (no ES)."""

import asyncio
import uuid

import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_cascade_refreshes_incoming_facets_once_and_skips_deleted(
    async_client, auth_headers, migrated_database, monkeypatch
) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from katalon.core.models import Relation
    from katalon.integrations import elasticsearch
    from katalon.workers import index_tasks

    async def record(path):
        response = await async_client.post(
            f"/v1/{path}", headers=auth_headers,
            json={"idno": uuid.uuid4().hex, "status": "public", "metadata_": {"label": "before"}},
        )
        assert response.status_code == 201, response.text
        return uuid.UUID(response.json()["id"])

    sender = await record("entities")
    receiver, reverse, deleted = [await record("objects") for _ in range(3)]
    response = await async_client.put(
        "/v1/portal/config", headers=auth_headers,
        json={"relation_facets": {"object": [{**_relation_facet(), "direction": "incoming"}]}},
    )
    assert response.status_code == 200, response.text
    engine = create_async_engine(migrated_database)
    try:
        async with async_sessionmaker(engine)() as session:
            for source_type, source, target_type, target, kind in (
                ("entity", sender, "object", receiver, "komponist"),
                ("entity", sender, "object", receiver, "second"),
                ("object", reverse, "entity", sender, "komponist"),
                ("entity", sender, "object", deleted, "komponist"),
                ("entity", sender, "entity", sender, "self"),
            ):
                session.add(Relation(from_type=source_type, from_id=source, to_type=target_type,
                                     to_id=target, relation_type=kind, metadata_={}))
            await session.execute(text("UPDATE objects SET deleted_at = now() WHERE id = :id"), {"id": deleted})
            await session.execute(text("UPDATE entities SET metadata = '{\"label\": \"after\"}' WHERE id = :id"), {"id": sender})
            await session.commit()

        writes = []

        async def write(record_id, doc):
            writes.append((record_id, doc))

        monkeypatch.setattr(elasticsearch, "index_document", write)
        result = await asyncio.to_thread(index_tasks.cascade_reindex_task.run, "entity", str(sender))
        assert result["cascaded"] == 2
        assert {record_id for record_id, _ in writes} == {str(receiver), str(reverse)}
        assert next(doc for record_id, doc in writes if record_id == str(receiver))["facet_rel_komponist"] == [f"{sender}|after"]

        async with engine.begin() as conn:
            await conn.execute(text("UPDATE entities SET status = 'draft' WHERE id = :id"), {"id": sender})
        writes.clear()
        await asyncio.to_thread(index_tasks.cascade_reindex_task.run, "entity", str(sender))
        assert next(doc for record_id, doc in writes if record_id == str(receiver))["facet_rel_komponist"] == []
    finally:
        await engine.dispose()


@pytest.fixture
def reindex_requests(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []
    monkeypatch.setattr(
        "katalon.workers.reindex_state.request_bulk_reindex", lambda t, **_k: calls.append(t)
    )
    return calls


def _relation_facet(key: str = "komponist") -> dict:
    return {
        "key": key,
        "label": {"de": "Komponist_in"},
        "target_type": "entity",
        "relation_types": ["komponist"],
    }


@pytest.mark.asyncio
async def test_relation_facets_are_listed_ordered_and_trigger_reindex(
    async_client, auth_headers, reindex_requests
) -> None:
    field = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "object",
            "name": f"fc_{uuid.uuid4().hex[:6]}",
            "label": {"de": "Feld"},
            "field_type": "text",
            "is_facet": True,
        },
    )
    name = field.json()["name"]
    reindex_requests.clear()

    response = await async_client.put(
        "/v1/portal/config",
        headers=auth_headers,
        json={
            "relation_facets": {"object": [_relation_facet()]},
            "facet_order": {"object": ["relfacet_komponist", name]},
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["facet_fields"]["object"][:2] == ["relfacet_komponist", name]
    assert body["facet_kinds"]["object"]["relfacet_komponist"] == {
        "kind": "relation",
        "label": {"de": "Komponist_in"},
    }
    assert reindex_requests == ["object"]

    # Unchanged relation facets: no rebuild; order-only change: no rebuild.
    reindex_requests.clear()
    response = await async_client.put(
        "/v1/portal/config",
        headers=auth_headers,
        json={"relation_facets": {"object": [_relation_facet()]}, "facet_order": {"object": []}},
    )
    assert response.status_code == 200
    assert reindex_requests == []


@pytest.mark.asyncio
async def test_relation_facet_validation(async_client, auth_headers) -> None:
    for bad in (
        {"object": [_relation_facet("Komponist!")]},
        {"object": [_relation_facet(), _relation_facet()]},
        {"object": [{**_relation_facet(), "relation_types": []}]},
        {"object": [{**_relation_facet(), "direction": "sideways"}]},
    ):
        response = await async_client.put(
            "/v1/portal/config", headers=auth_headers, json={"relation_facets": bad}
        )
        assert response.status_code == 422, bad


@pytest.mark.asyncio
async def test_date_granularity_validation_and_reindex(
    async_client, auth_headers, reindex_requests
) -> None:
    async def create(field_type: str, settings: dict) -> object:
        return await async_client.post(
            "/v1/schema",
            headers=auth_headers,
            json={
                "target_type": "object",
                "name": f"dg_{uuid.uuid4().hex[:6]}",
                "label": {"de": "Datum"},
                "field_type": field_type,
                "settings": settings,
            },
        )

    assert (await create("text", {"facet_granularity": "decade"})).status_code == 422
    assert (await create("date", {"facet_granularity": "week"})).status_code == 422
    created = await create("date", {})
    assert created.status_code == 201
    field = created.json()
    reindex_requests.clear()

    body = {k: v for k, v in field.items() if k not in ("id", "children")}
    body["settings"] = {"facet_granularity": "decade"}
    response = await async_client.put(f"/v1/schema/{field['id']}", headers=auth_headers, json=body)
    assert response.status_code == 200, response.text
    assert reindex_requests == ["object"]


@pytest.mark.asyncio
async def test_moving_a_term_reindexes_types_using_the_vocabulary(
    async_client, auth_headers, reindex_requests
) -> None:
    vocab = (
        await async_client.post(
            "/v1/vocabularies",
            headers=auth_headers,
            json={"name": f"tv_{uuid.uuid4().hex[:6]}", "is_hierarchical": True},
        )
    ).json()

    async def term(name: str) -> str:
        response = await async_client.post(
            f"/v1/vocabularies/{vocab['id']}/terms",
            headers=auth_headers,
            json={"vocabulary_id": vocab["id"], "term": name, "label": {"de": name}},
        )
        assert response.status_code == 201, response.text
        return str(response.json()["id"])

    parent, child = await term("Natur"), await term("Tiere")
    await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "place",
            "name": f"tv_{uuid.uuid4().hex[:6]}",
            "label": {"de": "Schlagwort"},
            "field_type": "vocab",
            "settings": {"vocabulary_id": vocab["id"]},
        },
    )
    reindex_requests.clear()

    response = await async_client.put(
        f"/v1/vocabularies/terms/{child}", headers=auth_headers, json={"parent_id": parent}
    )
    assert response.status_code == 200, response.text
    assert reindex_requests == ["place"]

    reindex_requests.clear()
    response = await async_client.put(
        f"/v1/vocabularies/terms/{child}", headers=auth_headers, json={"label": {"de": "Tiere!"}}
    )
    assert response.status_code == 200
    assert reindex_requests == []


@pytest.mark.asyncio
async def test_unknown_facets_are_not_aggregated(
    async_client, auth_headers, fake_es, monkeypatch
) -> None:
    """Anonymous callers may only aggregate configured facets (docs carry
    facet_all_* for every public field)."""
    captured: dict = {}

    async def fake_search(**kwargs):
        captured.update(kwargs)
        return {"total": 0, "page": 1, "page_size": 20, "items": [], "facets": {}, "numeric_facets": {}}

    monkeypatch.setattr("katalon.services.search_service.search", fake_search)
    name = f"wl_{uuid.uuid4().hex[:6]}"
    await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={"target_type": "object", "name": name, "label": {"de": "x"}, "field_type": "text", "is_facet": True},
    )
    response = await async_client.get(
        "/portal/v1/search",
        params={"type": "object", "facets": f"{name},not_a_facet,related_places,inherited_entity_x"},
    )
    assert response.status_code == 200, response.text
    assert captured["facet_fields"] == [name]
