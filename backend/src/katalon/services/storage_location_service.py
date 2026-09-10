# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import StorageLocation


async def get_storage_location_subtree_ids(
    db: AsyncSession,
    root_id: uuid.UUID,
) -> list[uuid.UUID]:
    """Return root_id and all its recursive descendant storage location IDs.

    Uses a recursive CTE for fast single-roundtrip traversal (Building -> Room -> Shelf -> Box).
    """
    base_query = select(StorageLocation.id).where(
        StorageLocation.id == root_id,
        StorageLocation.deleted_at.is_(None),
    )

    cte = base_query.cte(name="storage_location_subtree", recursive=True)

    child_query = (
        select(StorageLocation.id)
        .join(cte, StorageLocation.parent_id == cte.c.id)
        .where(StorageLocation.deleted_at.is_(None))
    )

    cte = cte.union_all(child_query)

    stmt = select(cte.c.id)
    result = await db.execute(stmt)
    return list(result.scalars().all())
