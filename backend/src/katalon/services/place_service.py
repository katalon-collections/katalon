# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import Object, Place, Relation
from katalon.core.visibility import PUBLIC_STATUSES
from katalon.services.search_service import _extract_title


async def count_direct_children(db: AsyncSession, parent_id: uuid.UUID) -> int:
    """Count active places directly nested under ``parent_id``."""
    result = await db.execute(
        select(func.count()).where(Place.parent_id == parent_id, Place.deleted_at.is_(None))
    )
    return result.scalar_one()


async def reparent_children(
    db: AsyncSession, parent_id: uuid.UUID, new_parent_id: uuid.UUID | None
) -> None:
    """Move active direct children of ``parent_id`` to ``new_parent_id``."""
    await db.execute(
        update(Place)
        .where(Place.parent_id == parent_id, Place.deleted_at.is_(None))
        .values(parent_id=new_parent_id)
    )


async def get_place_subtree_ids(db: AsyncSession, root_id: uuid.UUID) -> list[uuid.UUID]:
    """Return ``root_id`` and all its recursive descendant place IDs (one recursive CTE)."""
    cte = (
        select(Place.id)
        .where(Place.id == root_id, Place.deleted_at.is_(None))
        .cte(name="place_subtree", recursive=True)
    )
    cte = cte.union_all(
        select(Place.id).join(cte, Place.parent_id == cte.c.id).where(Place.deleted_at.is_(None))
    )
    return list((await db.execute(select(cte.c.id))).scalars().all())


async def find_cycle_or_missing_parent(
    db: AsyncSession, place_id: uuid.UUID | None, parent_id: uuid.UUID | None
) -> str | None:
    """Return an error message when ``parent_id`` is not a valid parent for ``place_id``."""
    if parent_id is None:
        return None
    if place_id is not None and parent_id == place_id:
        return "Ein Ort kann nicht sein eigener übergeordneter Ort sein."
    parent = (
        await db.execute(select(Place).where(Place.id == parent_id, Place.deleted_at.is_(None)))
    ).scalar_one_or_none()
    if parent is None:
        return "Übergeordneter Ort existiert nicht."
    if place_id is None:
        return None
    visited = {place_id, parent_id}
    current = parent.parent_id
    while current is not None:
        if current == place_id:
            return "Zyklische Ortshierarchie ist nicht erlaubt."
        if current in visited:
            break
        visited.add(current)
        current = (
            await db.execute(select(Place.parent_id).where(Place.id == current))
        ).scalar_one_or_none()
    return None


@dataclass(frozen=True)
class PlaceNode:
    id: uuid.UUID
    parent_id: uuid.UUID | None
    title: str


async def load_place_nodes(db: AsyncSession, *, public_only: bool) -> dict[uuid.UUID, PlaceNode]:
    """All active places (public ones only for anonymous callers) as one id -> node map.

    Place trees are small (hundreds to a few thousand rows), so hierarchy views work on this
    map instead of one query per level. A place whose parent is not in the map counts as a root.
    """
    query = select(Place.id, Place.parent_id, Place.idno, Place.metadata_).where(
        Place.deleted_at.is_(None)
    )
    if public_only:
        query = query.where(Place.status.in_(PUBLIC_STATUSES))
    nodes: dict[uuid.UUID, PlaceNode] = {}
    for row in (await db.execute(query)).all():
        title = _extract_title(row.metadata_ or {}) or row.idno or str(row.id)[:8]
        nodes[row.id] = PlaceNode(row.id, row.parent_id, title)
    return nodes


def children_map(nodes: dict[uuid.UUID, PlaceNode]) -> dict[uuid.UUID | None, list[uuid.UUID]]:
    """Parent id -> child ids sorted by title; parents missing from ``nodes`` map to ``None``."""
    out: dict[uuid.UUID | None, list[uuid.UUID]] = {}
    for node in nodes.values():
        parent = node.parent_id if node.parent_id in nodes else None
        out.setdefault(parent, []).append(node.id)
    for ids in out.values():
        ids.sort(key=lambda i: nodes[i].title.casefold())
    return out


def ancestors_of(nodes: dict[uuid.UUID, PlaceNode], place_id: uuid.UUID) -> list[PlaceNode]:
    """Chain of visible ancestors, root first (empty for a root or an unknown place)."""
    chain: list[PlaceNode] = []
    seen = {place_id}
    current = nodes[place_id].parent_id if place_id in nodes else None
    while current is not None and current in nodes and current not in seen:
        seen.add(current)
        chain.insert(0, nodes[current])
        current = nodes[current].parent_id
    return chain


def subtree_counts(
    nodes: dict[uuid.UUID, PlaceNode], children: dict[uuid.UUID | None, list[uuid.UUID]]
) -> dict[uuid.UUID, int]:
    """Number of places in each node's subtree, the node itself included."""
    counts: dict[uuid.UUID, int] = {}
    order: list[uuid.UUID] = []
    stack = list(children.get(None, []))
    while stack:
        current = stack.pop()
        order.append(current)
        stack.extend(children.get(current, []))
    for place_id in reversed(order):
        counts[place_id] = 1 + sum(counts.get(c, 0) for c in children.get(place_id, []))
    return counts


def subtree_ids(
    children: dict[uuid.UUID | None, list[uuid.UUID]], root_id: uuid.UUID
) -> list[uuid.UUID]:
    """``root_id`` and every descendant, from an in-memory children map."""
    out: list[uuid.UUID] = []
    stack = [root_id]
    while stack:
        current = stack.pop()
        out.append(current)
        stack.extend(children.get(current, []))
    return out


async def objects_by_place(
    db: AsyncSession,
    *,
    relation_types: list[str],
    direction: str,
    public_only: bool,
) -> dict[uuid.UUID, set[uuid.UUID]]:
    """Object ids per place for a configured relation facet (relation types, direction)."""
    out: dict[uuid.UUID, set[uuid.UUID]] = {}
    pairs = []
    if direction in ("outgoing", "both"):
        pairs.append((Relation.from_type == "object", Relation.to_type == "place",
                      Relation.from_id, Relation.to_id))
    if direction in ("incoming", "both"):
        pairs.append((Relation.to_type == "object", Relation.from_type == "place",
                      Relation.to_id, Relation.from_id))
    for object_side, place_side, object_col, place_col in pairs:
        query = (
            select(object_col, place_col)
            .join(Object, Object.id == object_col)
            .where(object_side, place_side, Object.deleted_at.is_(None))
        )
        if relation_types:
            query = query.where(Relation.relation_type.in_(relation_types))
        if public_only:
            query = query.where(Object.status.in_(PUBLIC_STATUSES))
        for object_id, place_id in (await db.execute(query)).all():
            out.setdefault(place_id, set()).add(object_id)
    return out


def rolled_up_counts(
    children: dict[uuid.UUID | None, list[uuid.UUID]],
    objects: dict[uuid.UUID, set[uuid.UUID]],
) -> dict[uuid.UUID, int]:
    """Distinct objects in each place's subtree (an object in two sub-places counts once)."""
    sets: dict[uuid.UUID, set[uuid.UUID]] = {}
    order: list[uuid.UUID] = []
    stack = list(children.get(None, []))
    while stack:
        current = stack.pop()
        order.append(current)
        stack.extend(children.get(current, []))
    for place_id in reversed(order):
        merged = set(objects.get(place_id, ()))
        for child in children.get(place_id, []):
            merged |= sets[child]
        sets[place_id] = merged
    return {place_id: len(found) for place_id, found in sets.items()}


def tree_facet(
    nodes: dict[uuid.UUID, PlaceNode],
    children: dict[uuid.UUID | None, list[uuid.UUID]],
    active: list[uuid.UUID],
    expand: list[uuid.UUID],
    counts: dict[uuid.UUID, int] | None = None,
) -> dict[str, object]:
    """Portal tree facet over places, in the shape of the vocabulary tree facets.

    Counts are the places in each subtree (not narrowed by the query); ``nodes`` holds the
    root level plus the children of every expanded node, ``paths`` the chain of active values.
    """
    # Without explicit counts the facet counts places; with them (objects per place) empty
    # subtrees are left out.
    only_nonempty = counts is not None
    counts = counts if counts is not None else subtree_counts(nodes, children)

    def level(parent: uuid.UUID | None) -> list[dict[str, object]]:
        return [
            {
                "id": str(i),
                "label": {"und": nodes[i].title},
                "count": counts.get(i, 0 if only_nonempty else 1),
                "has_children": any(
                    counts.get(c, 0) > 0 or not only_nonempty for c in children.get(i, [])
                ),
            }
            for i in children.get(parent, [])
            if counts.get(i, 0 if only_nonempty else 1) > 0
        ]

    levels: dict[str, list[dict[str, object]]] = {"root": level(None)}
    for node_id in expand:
        if node_id in nodes:
            levels[str(node_id)] = level(node_id)
    paths = {
        str(value): [
            {"id": str(n.id), "label": {"und": n.title}}
            for n in [*ancestors_of(nodes, value), nodes[value]]
        ]
        for value in active
        if value in nodes
    }
    return {"nodes": levels, "paths": paths}
