from __future__ import annotations

import uuid

from sqlalchemy import and_, func, or_, select
from sqlalchemy import delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import Relation


async def count_relations(db: AsyncSession, record_type: str, record_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count()).where(
            or_(
                and_(Relation.from_type == record_type, Relation.from_id == record_id),
                and_(Relation.to_type == record_type, Relation.to_id == record_id),
            )
        )
    )
    return result.scalar_one()


async def delete_relations(db: AsyncSession, record_type: str, record_id: uuid.UUID) -> None:
    await db.execute(
        sa_delete(Relation).where(
            or_(
                and_(Relation.from_type == record_type, Relation.from_id == record_id),
                and_(Relation.to_type == record_type, Relation.to_id == record_id),
            )
        )
    )
