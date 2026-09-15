# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import StorageLocation


async def count_direct_children(db: AsyncSession, parent_id: uuid.UUID) -> int:
    """Count active storage locations directly nested under ``parent_id``."""
    result = await db.execute(
        select(func.count()).where(
            StorageLocation.parent_id == parent_id,
            StorageLocation.deleted_at.is_(None),
        )
    )
    return result.scalar_one()


async def reparent_children(
    db: AsyncSession, parent_id: uuid.UUID, new_parent_id: uuid.UUID | None
) -> None:
    """Move active direct children of ``parent_id`` to ``new_parent_id``."""
    await db.execute(
        update(StorageLocation)
        .where(
            StorageLocation.parent_id == parent_id,
            StorageLocation.deleted_at.is_(None),
        )
        .values(parent_id=new_parent_id)
    )


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
