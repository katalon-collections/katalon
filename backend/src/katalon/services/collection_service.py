# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import Collection
from katalon.core.visibility import PUBLIC_STATUSES
from katalon.services.search_service import _extract_title


async def get_collection_subtree_ids(
    db: AsyncSession,
    root_id: uuid.UUID,
    public_only: bool = False,
) -> list[uuid.UUID]:
    """Return root_id and all its recursive descendant collection IDs.

    Uses a recursive CTE for fast single-roundtrip traversal.
    """
    base_query = select(Collection.id).where(
        Collection.id == root_id,
        Collection.deleted_at.is_(None),
    )
    if public_only:
        base_query = base_query.where(Collection.status.in_(PUBLIC_STATUSES))

    cte = base_query.cte(name="collection_subtree", recursive=True)

    child_query = (
        select(Collection.id)
        .join(cte, Collection.parent_id == cte.c.id)
        .where(Collection.deleted_at.is_(None))
    )
    if public_only:
        child_query = child_query.where(Collection.status.in_(PUBLIC_STATUSES))

    cte = cte.union_all(child_query)

    stmt = select(cte.c.id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _collection_title(col: Collection) -> str:
    md = col.metadata_ or {}
    title = _extract_title(md)
    if not title:
        title = col.idno or str(col.id)
    return title


async def get_collection_subtree_titles(
    db: AsyncSession,
    identifier: str,
    public_only: bool = True,
) -> list[str]:
    """Resolve a collection title/idno/UUID to itself and all its descendant titles.

    Used by search filters to expand a collection query to cover sub-collections.
    If the collection is not found, returns [identifier].
    """
    target_uuid: uuid.UUID | None = None
    try:
        target_uuid = uuid.UUID(identifier)
    except (ValueError, TypeError):
        target_uuid = None

    query = select(Collection).where(Collection.deleted_at.is_(None))
    if public_only:
        query = query.where(Collection.status.in_(PUBLIC_STATUSES))

    all_cols = list((await db.execute(query)).scalars().all())
    if not all_cols:
        return [identifier]

    # Find matching root collection(s)
    roots: list[Collection] = []
    for c in all_cols:
        if (
            (target_uuid and c.id == target_uuid)
            or (c.idno and c.idno.strip() == identifier.strip())
            or _collection_title(c).strip().lower() == identifier.strip().lower()
        ):
            roots.append(c)

    if not roots:
        return [identifier]

    # Build parent -> children map in memory
    children_map: dict[uuid.UUID, list[Collection]] = {}
    for c in all_cols:
        if c.parent_id:
            children_map.setdefault(c.parent_id, []).append(c)

    result_titles: list[str] = [identifier]
    seen_ids: set[uuid.UUID] = set()

    for root in roots:
        queue = [root]
        while queue:
            curr = queue.pop(0)
            if curr.id in seen_ids:
                continue
            seen_ids.add(curr.id)
            title = _collection_title(curr)
            if title and title not in result_titles:
                result_titles.append(title)
            if curr.idno and curr.idno not in result_titles:
                result_titles.append(curr.idno)
            queue.extend(children_map.get(curr.id, []))

    return result_titles
