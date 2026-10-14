# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Portal facets end to end against a real Elasticsearch (BPK-like fixture).

Relation facets per relation type, date buckets from a repeatable group,
hierarchical vocabulary tree, unified facet order. Needs a reachable ES:
run with KATALON_TEST_ELASTICSEARCH=1 and ELASTICSEARCH_URL / ES_INDEX_NAME
set (the CI has no Elasticsearch, so the test is skipped there).
"""

import asyncio
import os
import uuid
from typing import Any

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    not os.environ.get("KATALON_TEST_ELASTICSEARCH"),
    reason="needs a real Elasticsearch (KATALON_TEST_ELASTICSEARCH=1)",
)


async def _post(client, headers, path: str, body: dict[str, Any]) -> dict[str, Any]:
    response = await client.post(path, headers=headers, json=body)
    assert response.status_code in (200, 201), response.text
    return response.json()


async def _field(client, headers, **body) -> dict[str, Any]:
    return await _post(
        client,
        headers,
        "/v1/schema",
        {"target_type": "object", "label": {"de": body["name"]}, **body},
    )


@pytest.mark.asyncio
async def test_portal_facets_against_real_elasticsearch(
    async_client, auth_headers, fake_reindex_redis
) -> None:
    from katalon.integrations import elasticsearch as es_module
    from katalon.workers import index_tasks

    c, h = async_client, auth_headers
    p = uuid.uuid4().hex[:6]

    # --- schema: date group with decade facet, hierarchical keyword field ---
    group = await _field(c, h, name=f"date_{p}", field_type="group", is_repeatable=True)
    await _field(
        c,
        h,
        name="dates_value",
        field_type="date",
        parent_id=group["id"],
        is_facet=True,
        settings={"facet_granularity": "decade"},
    )
    vocab = await _post(c, h, "/v1/vocabularies", {"name": f"sw_{p}", "is_hierarchical": True})

    async def term(name: str, parent: str | None = None) -> str:
        body = {"vocabulary_id": vocab["id"], "term": name, "label": {"de": name}}
        if parent:
            body["parent_id"] = parent
        return str((await _post(c, h, f"/v1/vocabularies/{vocab['id']}/terms", body))["id"])

    natur = await term("Natur")
    tiere = await term("Tiere", natur)
    hunde = await term("Hunde", tiere)
    musik = await term("Musik")
    await _field(
        c,
        h,
        name=f"sw_{p}",
        field_type="vocab",
        is_repeatable=True,
        is_facet=True,
        settings={"vocabulary_id": vocab["id"]},
    )

    # --- linked records: public composer, draft composer, painter, places ---
    async def record(path: str, label: str, status: str = "public") -> str:
        body = {"idno": f"{p}-{uuid.uuid4().hex[:6]}", "status": status, "metadata_": {"label": label}}
        return str((await _post(c, h, f"/v1/{path}", body))["id"])

    komponist = await record("entities", f"Komponist {p}")
    entwurf = await record("entities", f"Entwurf {p}", status="draft")
    maler = await record("entities", f"Maler {p}")
    ort_a = await record("places", f"Empfangsort {p}")
    ort_b = await record("places", f"Absendeort {p}")

    # --- relation facets + order ---
    response = await c.put(
        "/v1/portal/config",
        headers=h,
        json={
            "relation_facets": {
                "object": [
                    {
                        "key": "komponist",
                        "label": {"de": "Komponist_in"},
                        "target_type": "entity",
                        "relation_types": ["komponist"],
                    },
                    {
                        "key": "adressort",
                        "label": {"de": "Adress-/Absendeort"},
                        "target_type": "place",
                        "relation_types": ["wurde_empfangen", "wurde_abgesendet"],
                    },
                ]
            },
            "facet_order": {"object": ["relfacet_komponist", f"sw_{p}"]},
            "facet_fields": {"object": ["related_entities"]},
        },
    )
    assert response.status_code == 200, response.text
    config = (await c.get("/portal/v1/portal/config")).json()
    kinds = config["facet_kinds"]["object"]
    assert kinds["relfacet_komponist"]["kind"] == "relation"
    assert kinds[f"date_{p}__dates_value"] == {"kind": "date", "granularity": "decade"}
    assert kinds[f"sw_{p}"]["kind"] == "tree"
    assert config["facet_fields"]["object"][:2] == ["relfacet_komponist", f"sw_{p}"]

    # --- postcards ---
    async def karte(dates: list[str], terms: list[str], links: list[tuple[str, str, str]]) -> str:
        metadata = {
            "label": f"Karte {p}",
            f"date_{p}": [{"dates_value": d} for d in dates],
            f"sw_{p}": [{"id": t, "label": "x"} for t in terms],
        }
        body = {"idno": f"{p}-{uuid.uuid4().hex[:6]}", "status": "public", "metadata_": metadata}
        object_id = str((await _post(c, h, "/v1/objects", body))["id"])
        for to_type, to_id, rtype in links:
            await _post(
                c,
                h,
                "/v1/relations",
                {
                    "from_type": "object",
                    "from_id": object_id,
                    "to_type": to_type,
                    "to_id": to_id,
                    "relation_type": rtype,
                    "metadata_": {},
                },
            )
        return object_id

    k1 = await karte(
        ["1918-03-21", "1890/"],
        [hunde],
        [("entity", komponist, "komponist"), ("place", ort_a, "wurde_empfangen")],
    )
    k2 = await karte(
        ["1884/1919"],
        [tiere, musik],
        [("entity", entwurf, "komponist"), ("place", ort_b, "wurde_abgesendet")],
    )
    k3 = await karte(["0196-11-26"], [musik], [("entity", maler, "maler_zeichner")])
    await karte(["1925"], [], [("entity", komponist, "komponist")])  # stays draft below
    async with __import__("katalon.database", fromlist=["x"]).AsyncSessionLocal() as db:
        await db.execute(
            text("UPDATE objects SET status = 'draft' WHERE metadata->>'label' = :l AND idno NOT IN (SELECT idno FROM objects WHERE id IN (:a, :b, :c))"),
            {"l": f"Karte {p}", "a": uuid.UUID(k1), "b": uuid.UUID(k2), "c": uuid.UUID(k3)},
        )
        await db.commit()

    # --- index into a fresh index ---
    # The app fixture stubs ensure_index(); create the live alias explicitly.
    if not await es_module.get_es().indices.exists(index=es_module.INDEX_NAME):
        await es_module.create_physical_index(es_module.new_physical_index_name(), alias=True)
    report = await asyncio.to_thread(index_tasks.bulk_reindex_type_task.run, "object")
    assert report["status"] == "ok", report

    async def search(**params: Any) -> dict[str, Any]:
        facets = ",".join(
            [f"date_{p}__dates_value", f"sw_{p}", "relfacet_komponist", "relfacet_adressort", "related_entities"]
        )
        query: list[tuple[str, str]] = [("type", "object"), ("facets", facets), ("q", p)]
        for key, value in params.items():
            for v in value if isinstance(value, list) else [value]:
                query.append((key, v))
        response = await c.get("/portal/v1/search", params=query)
        assert response.status_code == 200, response.text
        return response.json()

    result = await search()
    assert result["total"] == 3  # the fourth card is draft
    facets = result["facets"]

    # Date: decades from all group instances, chronological, 0196 ignored.
    decades = [b["value"] for b in facets[f"meta_date_{p}__dates_value"]]
    assert decades == ["1880", "1890", "1900", "1910"]
    by_decade = {b["value"]: b["count"] for b in facets[f"meta_date_{p}__dates_value"]}
    assert by_decade == {"1880": 1, "1890": 2, "1900": 1, "1910": 2}

    # Relation facets: only the public composer, and only via "komponist".
    komponist_buckets = facets["meta_relfacet_komponist"]
    assert [b["value"] for b in komponist_buckets] == [f"{komponist}|Komponist {p}"]
    assert komponist_buckets[0]["count"] == 1
    adress = {b["value"].split("|")[0]: b["count"] for b in facets["meta_relfacet_adressort"]}
    assert adress == {ort_a: 1, ort_b: 1}
    # related_entities no longer leaks draft titles.
    related = {b["value"] for b in facets["related_entities"]}
    assert f"Entwurf {p}" not in related and f"Maler {p}" in related

    # SQL cross-check of the relation facet against relations of public objects.
    async with __import__("katalon.database", fromlist=["x"]).AsyncSessionLocal() as db:
        expected = (
            await db.execute(
                text(
                    "SELECT count(DISTINCT r.from_id) FROM relations r "
                    "JOIN objects o ON o.id = r.from_id JOIN entities e ON e.id = r.to_id "
                    "WHERE r.relation_type = 'komponist' AND o.status IN ('public','published') "
                    "AND o.deleted_at IS NULL AND e.status IN ('public','published') "
                    "AND e.deleted_at IS NULL AND o.idno LIKE :p"
                ),
                {"p": f"{p}-%"},
            )
        ).scalar_one()
    assert sum(b["count"] for b in komponist_buckets) == expected

    # Tree: top level with counts, expand, filter includes descendants.
    tree = result["tree_facets"][f"sw_{p}"]
    root = {n["id"]: n for n in tree["nodes"]["root"]}
    assert root[natur]["count"] == 2 and root[natur]["has_children"] is True
    assert root[musik]["count"] == 2
    expanded = await search(**{f"expand_sw_{p}": natur})
    children = expanded["tree_facets"][f"sw_{p}"]["nodes"][natur]
    assert [(n["id"], n["count"]) for n in children] == [(tiere, 2)]

    filtered = await search(**{f"meta_sw_{p}": natur})
    assert {i["id"] for i in filtered["items"]} == {k1, k2}
    path = filtered["tree_facets"][f"sw_{p}"]["paths"][natur]
    assert [step["id"] for step in path] == [natur]
    deep = await search(**{f"meta_sw_{p}": hunde})
    assert [step["id"] for step in deep["tree_facets"][f"sw_{p}"]["paths"][hunde]] == [natur, tiere, hunde]

    # Relation facet filter by id; date bucket filter.
    by_komponist = await search(meta_relfacet_komponist=komponist)
    assert {i["id"] for i in by_komponist["items"]} == {k1}
    by_decade_filter = await search(**{f"meta_date_{p}__dates_value": "1880"})
    assert {i["id"] for i in by_decade_filter["items"]} == {k2}
