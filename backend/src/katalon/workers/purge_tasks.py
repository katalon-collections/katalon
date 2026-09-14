# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Coroutine
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import Collection, Entity, Object, Occurrence, Place, StorageLocation
from katalon.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Procedure is intentionally excluded: it has no deleted_at / soft-delete
# lifecycle (see Procedure.archive()) — it is archived, not soft-deleted,
# so there is nothing for a retention-window purge to act on.
_PURGEABLE_MODELS: dict[str, Any] = {
    "object": Object,
    "entity": Entity,
    "place": Place,
    "occurrence": Occurrence,
    "collection": Collection,
    "storage_location": StorageLocation,
}
_MODEL_MAP = _PURGEABLE_MODELS


def _run[T](coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)


async def _purge_type(session: AsyncSession, model: Any, record_type: str, cutoff: datetime) -> int:
    from katalon.core.models import MediaFile
    from katalon.services.audit_service import log_change
    from katalon.services.media_deletion_service import finalize_pending_delete, mark_pending_delete
    from katalon.services.relation_cleanup_service import cleanup_relation_refs
    from katalon.services.relation_service import delete_relations

    result = await session.execute(
        select(model).where(model.deleted_at.is_not(None), model.deleted_at < cutoff)
    )
    records = result.scalars().all()

    # Phase 1: commit every to-be-purged record's media deletion intent before
    # touching storage at all. A crash or rollback here leaves every physical
    # file untouched — the next run picks the same rows back up via the
    # deleted_at IS NOT NULL sweep in phase 2.
    media_by_record: dict[uuid.UUID, list[MediaFile]] = {}
    if record_type == "object":
        for record in records:
            media_result = await session.execute(
                select(MediaFile).where(MediaFile.object_id == record.id)
            )
            files = list(media_result.scalars().all())
            for media in files:
                if media.deleted_at is None:
                    mark_pending_delete(media)
            media_by_record[record.id] = files
        if any(media_by_record.values()):
            await session.commit()

    # Phase 2: only now attempt physical deletion — idempotent and safe to
    # repeat. A record is hard-deleted only once every one of its media
    # files is confirmed gone from storage: media_files.object_id cascades
    # on delete (passive_deletes=True), so hard-deleting the record first
    # would silently destroy the only durable trace of a file that still
    # exists in storage. A record with still-pending media is deferred to
    # the next run instead — it stays soft-deleted, past cutoff, and gets
    # retried automatically.
    purged = 0
    for record in records:
        files = media_by_record.get(record.id, [])
        all_removed = True
        for media in files:
            if await finalize_pending_delete(media):
                await session.delete(media)
            else:
                all_removed = False
        if not all_removed:
            logger.warning(
                "Purge deferred for %s %s — one or more media files are still pending "
                "physical deletion and will be retried on the next run",
                record_type,
                record.id,
            )
            continue
        await delete_relations(session, record_type, record.id)
        await cleanup_relation_refs(session, record_type, record.id, cutoff=cutoff)
        await log_change(
            session, record_type=record_type, record_id=record.id, user_id=None, action="purge"
        )
        await session.delete(record)
        purged += 1
    return purged


async def _do_purge() -> dict[str, int]:
    from katalon.config import settings
    from katalon.database import AsyncSessionLocal
    from katalon.workers.enqueue import run_after_commit_hooks

    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=settings.purge_after_days)
    totals: dict[str, int] = {}
    async with AsyncSessionLocal() as session:
        for record_type, model in _PURGEABLE_MODELS.items():
            totals[record_type] = await _purge_type(session, model, record_type, cutoff)
        await session.commit()
        await run_after_commit_hooks(session)
    return totals


@celery_app.task(name="katalon.purge_soft_deleted")
def purge_soft_deleted() -> dict[str, int]:
    """Hard-delete soft-deleted records past the retention window (all record types
    with a deleted_at lifecycle; see _do_purge for the explicit Procedure exclusion)."""
    return _run(_do_purge())


async def _sweep_pending_media() -> dict[str, int]:
    from katalon.database import AsyncSessionLocal
    from katalon.services.media_deletion_service import sweep_pending_media_deletes

    async with AsyncSessionLocal() as session:
        report = await sweep_pending_media_deletes(session)
        await session.commit()
    return report


@celery_app.task(name="katalon.sweep_pending_media_deletes")
def sweep_pending_media_deletes_task() -> dict[str, int]:
    """Retry physical storage deletion for every MediaFile row whose deletion intent
    is already committed but physical cleanup has not (yet) fully succeeded —
    worker crash between phases, storage outage, or S3 partial-batch failure.
    Idempotent; safe to run frequently (see celery_app.conf.beat_schedule)."""
    return _run(_sweep_pending_media())
