from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.media_storage import storage_path
from katalon.workers.celery_app import celery_app


def _run[T](coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)


async def _purge_type(session: AsyncSession, model: Any, record_type: str, cutoff: datetime) -> int:
    from katalon.core.models import MediaFile
    from katalon.services.audit_service import log_change
    from katalon.services.relation_service import delete_relations

    result = await session.execute(
        select(model).where(model.deleted_at.is_not(None), model.deleted_at < cutoff)
    )
    records = result.scalars().all()
    for record in records:
        if record_type == "object":
            media_result = await session.execute(
                select(MediaFile).where(MediaFile.object_id == record.id)
            )
            for media in media_result.scalars().all():
                storage_path(media.storage_key).unlink(missing_ok=True)
                if media.iiif_storage_key:
                    storage_path(media.iiif_storage_key).unlink(missing_ok=True)
        await delete_relations(session, record_type, record.id)
        await log_change(session, record_type=record_type, record_id=record.id, user_id=None, action="purge")
        await session.delete(record)
    return len(records)


async def _do_purge() -> dict[str, int]:
    from katalon.config import settings
    from katalon.core.models import Entity, Object, Occurrence, Place
    from katalon.database import AsyncSessionLocal

    model_map: dict[str, Any] = {
        "object": Object,
        "entity": Entity,
        "place": Place,
        "occurrence": Occurrence,
    }
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=settings.purge_after_days)
    totals: dict[str, int] = {}
    async with AsyncSessionLocal() as session:
        for record_type, model in model_map.items():
            totals[record_type] = await _purge_type(session, model, record_type, cutoff)
        await session.commit()
    return totals


@celery_app.task(name="katalon.purge_soft_deleted")
def purge_soft_deleted() -> dict[str, int]:
    """Hard-delete soft-deleted objects/entities/places/occurrences past the retention window."""
    return _run(_do_purge())
