# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid
from typing import Any

import pytest

from katalon.services import place_service
from katalon.services.place_service import (
    PlaceNode,
    ancestors_of,
    children_map,
    subtree_counts,
    subtree_ids,
    tree_facet,
)


def _tree() -> tuple[dict[uuid.UUID, PlaceNode], dict[str, uuid.UUID]]:
    ids = {name: uuid.uuid4() for name in ("de", "mv", "sn", "ls", "fr")}
    parents = {"de": None, "mv": "de", "sn": "mv", "ls": "sn", "fr": None}
    titles = {"de": "Deutschland", "mv": "MV", "sn": "Schwerin", "ls": "Lankower See", "fr": "Frankreich"}
    nodes = {
        ids[k]: PlaceNode(ids[k], ids[parents[k]] if parents[k] else None, titles[k]) for k in ids
    }
    return nodes, ids


def test_tree_helpers() -> None:
    nodes, ids = _tree()
    kids = children_map(nodes)
    assert [nodes[i].title for i in ancestors_of(nodes, ids["ls"]) and [a.id for a in ancestors_of(nodes, ids["ls"])]] == [
        "Deutschland",
        "MV",
        "Schwerin",
    ]
    assert set(subtree_ids(kids, ids["mv"])) == {ids["mv"], ids["sn"], ids["ls"]}
    counts = subtree_counts(nodes, kids)
    assert (counts[ids["de"]], counts[ids["mv"]], counts[ids["fr"]]) == (4, 3, 1)


def test_hidden_parent_makes_a_root() -> None:
    nodes, ids = _tree()
    del nodes[ids["mv"]]  # e.g. a draft parent, not visible to the public
    kids = children_map(nodes)
    assert ids["sn"] in kids[None]
    assert ancestors_of(nodes, ids["ls"]) == [nodes[ids["sn"]]]


def test_tree_facet_levels_and_paths() -> None:
    nodes, ids = _tree()
    facet = tree_facet(nodes, children_map(nodes), active=[ids["sn"]], expand=[ids["de"]])
    roots = facet["nodes"]["root"]  # type: ignore[index]
    assert [r["label"]["und"] for r in roots] == ["Deutschland", "Frankreich"]
    assert roots[0]["count"] == 4 and roots[0]["has_children"] is True
    assert [n["label"]["und"] for n in facet["nodes"][str(ids["de"])]] == ["MV"]  # type: ignore[index]
    assert [p["label"]["und"] for p in facet["paths"][str(ids["sn"])]] == [  # type: ignore[index]
        "Deutschland",
        "MV",
        "Schwerin",
    ]


def test_object_counts_roll_up_distinct_and_hide_empty_places() -> None:
    from katalon.services.place_service import rolled_up_counts

    nodes, ids = _tree()
    kids = children_map(nodes)
    o1, o2 = uuid.uuid4(), uuid.uuid4()
    # o1 sits in two places of the same subtree and must count once for Deutschland.
    counts = rolled_up_counts(kids, {ids["ls"]: {o1, o2}, ids["sn"]: {o1}})
    assert (counts[ids["de"]], counts[ids["mv"]], counts[ids["sn"]], counts[ids["fr"]]) == (2, 2, 2, 0)
    facet = tree_facet(nodes, kids, active=[], expand=[], counts=counts)
    assert [n["label"]["und"] for n in facet["nodes"]["root"]] == ["Deutschland"]  # type: ignore[index]


@pytest.mark.asyncio
async def test_load_place_chains_walks_only_parent_levels(monkeypatch: pytest.MonkeyPatch) -> None:
    nodes, ids = _tree()
    calls: list[set[uuid.UUID]] = []

    async def _load(_db: Any, *, public_only: bool, ids: set[uuid.UUID]) -> dict[uuid.UUID, PlaceNode]:
        calls.append(ids)
        return {i: nodes[i] for i in ids if i in nodes}

    monkeypatch.setattr(place_service, "load_place_nodes", _load)
    found = await place_service.load_place_chains(None, {ids["ls"]}, public_only=True)  # type: ignore[arg-type]
    assert [n.title for n in ancestors_of(found, ids["ls"])] == ["Deutschland", "MV", "Schwerin"]
    assert len(calls) == 4
    assert ids["fr"] not in found
