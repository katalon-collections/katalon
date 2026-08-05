"""Optimistic locking helper for record updates.

Records carry a monotonically increasing ``version``. A client that loaded a
record at version N sends ``If-Match: N`` on update. If the stored version has
moved on (someone else saved in the meantime), we refuse with 409 instead of
silently overwriting their change (last-write-wins).

The check is only enforced when the client supplies ``If-Match`` — scripts and
the importer that do not send it keep their previous behaviour; the admin UI
always sends it.
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
    """Require an optimistic-lock token for destructive state replacement."""
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
        constraint = getattr(exc.orig, "constraint_name", "") or ""
        await db.rollback()
        if constraint.endswith("_idno_key") or (
            constraint.startswith("ix_") and constraint.endswith("_idno")
        ):
            raise HTTPException(status_code=400, detail="ID-Nr. bereits vergeben.") from None
        raise
