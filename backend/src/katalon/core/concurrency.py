# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Optimistic locking helper for record updates.

Records carry a monotonically increasing ``version``. A client that loaded a
record at version N sends ``If-Match: N`` on update. If the stored version has
moved on (someone else saved in the meantime), we refuse with 409 instead of
silently overwriting their change (last-write-wins).

Every REST update/publish/restore endpoint requires ``If-Match``
(``require_version()`` — 428 if missing, 409 on mismatch). No known
installation predates this contract (#396 follow-up), so it applies
uniformly with no legacy opt-out. ``check_version()`` (409-only, no 428) is
kept as the shared comparison ``require_version()`` builds on; it has no
direct REST caller left. The importer and batch-edit Celery tasks never go
through these HTTP endpoints at all — they write via the service layer
directly, which has no per-record "expected version" concept for a bulk
upsert — so they are structurally unaffected, not exempted by a header
check.
"""

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError


def check_version(current_version: int, if_match: int | None) -> None:
    """Raise 409 if the client's expected version no longer matches the record.

    On mismatch the client re-fetches the current server state and resolves the
    conflict (see the admin UI merge dialog).
    """
    if if_match is not None and if_match != current_version:
        raise HTTPException(
            status_code=409,
            detail={"error": "version_conflict", "current_version": current_version},
        )


def require_version(current_version: int, if_match: int | None) -> None:
    """Require an optimistic-lock token. Used by every update/publish/restore
    endpoint, not only destructive state replacement — a missing token is
    ambiguous (client on old codebase, hand-crafted request, curl without the
    header) and last-write-wins is never the safe default to fall back to.
    """
    if if_match is None:
        raise HTTPException(status_code=428, detail="If-Match header required")
    check_version(current_version, if_match)


async def flush_record(db: AsyncSession, record: Any) -> None:
    """Flush a versioned record and expose concurrency/IDNO conflicts as API errors."""
    record_id = record.id
    model = type(record)
    try:
        await db.flush()
    except StaleDataError:
        await db.rollback()
        current_version = await db.scalar(select(model.version).where(model.id == record_id))
        raise HTTPException(
            status_code=409,
            detail={"error": "version_conflict", "current_version": current_version},
        ) from None
    except IntegrityError as exc:
        # asyncpg errors arrive wrapped in SQLAlchemy's plain DBAPI-compat
        # exception (no constraint_name); the real asyncpg exception with the
        # diagnostic fields is chained on as __cause__.
        constraint = (
            getattr(exc.orig, "constraint_name", None)
            or getattr(getattr(exc.orig, "__cause__", None), "constraint_name", None)
            or ""
        )
        await db.rollback()
        if constraint.endswith("_idno_key") or (
            constraint.startswith("ix_") and constraint.endswith("_idno")
        ):
            raise HTTPException(status_code=400, detail="ID-Nr. bereits vergeben.") from None
        raise
