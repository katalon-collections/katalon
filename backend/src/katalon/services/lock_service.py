# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Manual Exclusive Lock — persistent per-record lock, survives sessions.

Differs from Presence Lock (ephemeral heartbeat): ResourceLock is set
explicitly by the user, lasts up to 7 days, and requires Force Unlock
by admin when the owner cannot release it themselves.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import ResourceLock, User

MAX_LOCK_DAYS = 7


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass
class LockInfo:
    locked_by: uuid.UUID
    locked_by_email: str
    locked_at: datetime
    expires_at: datetime | None
    reason: str


async def set_lock(
    db: AsyncSession,
    resource_type: str,
    resource_id: uuid.UUID,
    user: User,
    reason: str = "",
    expires_at: datetime | None = None,
) -> LockInfo:
    if expires_at is None:
        expires_at = _now() + timedelta(days=MAX_LOCK_DAYS)
    if expires_at > _now() + timedelta(days=MAX_LOCK_DAYS):
        expires_at = _now() + timedelta(days=MAX_LOCK_DAYS)

    existing = await get_lock(db, resource_type, resource_id)
    if existing and existing.locked_by != user.id:
        raise HTTPException(
            status_code=409,
            detail={"error": "resource_locked", "locked_by": existing.locked_by_email},
        )

    await db.execute(
        delete(ResourceLock).where(
            ResourceLock.resource_type == resource_type,
            ResourceLock.resource_id == resource_id,
        )
    )
    lock = ResourceLock(
        resource_type=resource_type,
        resource_id=resource_id,
        locked_by=user.id,
        locked_at=_now(),
        expires_at=expires_at,
        reason=reason,
    )
    db.add(lock)
    await db.flush()
    return LockInfo(
        locked_by=user.id,
        locked_by_email=user.email,
        locked_at=_now(),
        expires_at=expires_at,
        reason=reason,
    )


async def release_lock(
    db: AsyncSession,
    resource_type: str,
    resource_id: uuid.UUID,
    user: User,
) -> bool:
    existing = await get_lock(db, resource_type, resource_id)
    if not existing:
        return False
    if existing.locked_by != user.id:
        raise HTTPException(
            status_code=403,
            detail="Nur der Besitzer der Sperre kann sie aufheben.",
        )
    await db.execute(
        delete(ResourceLock).where(
            ResourceLock.resource_type == resource_type,
            ResourceLock.resource_id == resource_id,
        )
    )
    await db.flush()
    return True


async def force_unlock(
    db: AsyncSession,
    resource_type: str,
    resource_id: uuid.UUID,
    admin_user: User,
) -> bool:
    existing = await get_lock(db, resource_type, resource_id)
    if not existing:
        return False
    await db.execute(
        delete(ResourceLock).where(
            ResourceLock.resource_type == resource_type,
            ResourceLock.resource_id == resource_id,
        )
    )
    await db.flush()
    return True


async def get_lock(
    db: AsyncSession, resource_type: str, resource_id: uuid.UUID
) -> LockInfo | None:
    result = await db.execute(
        select(ResourceLock, User.email)
        .join(User, User.id == ResourceLock.locked_by, isouter=True)
        .where(
            ResourceLock.resource_type == resource_type,
            ResourceLock.resource_id == resource_id,
            (ResourceLock.expires_at.is_(None)) | (ResourceLock.expires_at > _now()),
        )
    )
    row = result.one_or_none()
    if not row:
        return None
    lock, email = row
    return LockInfo(
        locked_by=lock.locked_by,
        locked_by_email=email or "",
        locked_at=lock.locked_at,
        expires_at=lock.expires_at,
        reason=lock.reason,
    )


async def get_active_locks_for_user(
    db: AsyncSession, user_id: uuid.UUID
) -> list[LockInfo]:
    result = await db.execute(
        select(ResourceLock, User.email)
        .join(User, User.id == ResourceLock.locked_by, isouter=True)
        .where(
            ResourceLock.locked_by == user_id,
            (ResourceLock.expires_at.is_(None)) | (ResourceLock.expires_at > _now()),
        )
    )
    return [
        LockInfo(
            locked_by=lock.locked_by,
            locked_by_email=email or "",
            locked_at=lock.locked_at,
            expires_at=lock.expires_at,
            reason=lock.reason,
        )
        for lock, email in result.all()
    ]


async def enforce_not_locked(
    db: AsyncSession, resource_type: str, resource_id: uuid.UUID, current_user: User
) -> None:
    """Raise 409 if someone else holds a manual lock on this record."""
    lock = await get_lock(db, resource_type, resource_id)
    if lock and lock.locked_by != current_user.id:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "resource_locked",
                "locked_by": lock.locked_by_email,
                "reason": lock.reason,
            },
        )