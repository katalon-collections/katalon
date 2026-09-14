# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Rollback-safe, idempotent media deletion lifecycle (#390).

Both the manual media delete endpoint and the automatic purge worker used to
remove the physical file before the database row, so a later DB rollback or
failure left an already-gone original next to a still-valid ``MediaFile``
row. The fix splits deletion into two durable phases:

1. ``mark_pending_delete`` records the deletion intent on the row. The
   caller MUST commit this before any physical deletion is attempted — a
   crash or rollback before that commit leaves the file untouched.
2. ``finalize_pending_delete``/``finalize_pending_deletes`` perform the
   actual, idempotent storage deletion against an already-committed
   pending row, and only then remove the DB row. A storage failure (outage,
   permission error, S3 partial-batch failure) leaves the row exactly as it
   was — a visible, retryable "pending delete" marker, never a silently
   successful or silently lost deletion.

Callers: the manual delete endpoint (``api/v1/media.py``) runs both phases
inline; the purge worker (``workers/purge_tasks.py``) does the same across a
whole batch; ``katalon.sweep_pending_media_deletes`` (Celery Beat) retries
any row phase 2 did not clear — including after a worker crash between the
two phases.
"""

import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.media_storage import StorageDeleteError, get_storage
from katalon.core.models import MediaFile

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def mark_pending_delete(media: MediaFile) -> None:
    """Record the deletion intent. The caller MUST commit before calling
    ``finalize_pending_delete`` — that commit is what makes the intent
    durable against a later DB rollback or process crash."""
    media.deleted_at = _now()


def _storage_keys(media: MediaFile) -> list[str]:
    keys = [media.storage_key]
    if media.iiif_storage_key:
        keys.append(media.iiif_storage_key)
    return keys


async def finalize_pending_delete(media: MediaFile) -> bool:
    """Idempotently remove a pending-delete row's storage objects.

    Safe to call repeatedly — after a crash, on a scheduled retry, or twice
    in a row for the same media — because both backends treat an
    already-missing key as already deleted. Returns True once every
    storage object for this row is confirmed gone, at which point the
    caller may hard-delete the DB row. Returns False, leaving the row
    untouched, when at least one object could not be removed.
    """
    if media.deleted_at is None:
        raise ValueError(
            f"MediaFile {media.id} has no committed deletion intent — "
            "call mark_pending_delete() and commit before finalizing"
        )
    try:
        await get_storage().delete(*_storage_keys(media))
    except StorageDeleteError as exc:
        logger.warning(
            "Physical media delete still pending for %s — retry needed: %s",
            media.id, exc.failures,
        )
        return False
    return True


async def finalize_pending_deletes(
    db: AsyncSession, media_files: Sequence[MediaFile]
) -> list[uuid.UUID]:
    """Finalize a batch of pending-delete rows. Returns the ids that were
    fully removed from storage and deleted from the DB; every other id in
    ``media_files`` remains a pending-delete row for the next retry."""
    finalized: list[uuid.UUID] = []
    for media in media_files:
        if await finalize_pending_delete(media):
            finalized.append(media.id)
            await db.delete(media)
    return finalized


async def sweep_pending_media_deletes(db: AsyncSession) -> dict[str, int]:
    """Retry physical deletion for every row whose deletion intent is
    already committed. Covers a worker crash between intent-commit and
    physical delete, a transient storage outage, and S3 partial-batch
    failures that left specific keys undeleted. Idempotent — safe to run on
    an arbitrary schedule (see ``katalon.sweep_pending_media_deletes``)."""
    result = await db.execute(select(MediaFile).where(MediaFile.deleted_at.is_not(None)))
    pending = list(result.scalars().all())
    finalized = await finalize_pending_deletes(db, pending)
    return {
        "pending": len(pending),
        "finalized": len(finalized),
        "still_pending": len(pending) - len(finalized),
    }
