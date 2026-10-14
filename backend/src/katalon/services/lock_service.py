# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Manual Exclusive Lock — persistent per-record lock, survives sessions.

Differs from Presence Lock (ephemeral heartbeat): ResourceLock is set
explicitly by the user, lasts until released or force-unlocked by admin.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import (
    Collection,
    Entity,
    Object,
    Occurrence,
    Place,
    Procedure,
    ResourceLock,
    StorageLocation,
    User,
)
from katalon.services.search_service import _extract_title


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass
class LockInfo:
    locked_by: uuid.UUID
    locked_by_email: str
    locked_at: datetime
    expires_at: datetime | None
    reason: str
    resource_type: str = ""
    resource_id: uuid.UUID | None = None
    title: str | None = None
    idno: str | None = None


async def set_lock(
    db: AsyncSession,
    resource_type: str,
    resource_id: uuid.UUID,
    user: User,
    reason: str = "",
    expires_at: datetime | None = None,
) -> LockInfo:
    existing = await get_lock(db, resource_type, resource_id)
    if existing and existing.locked_by != user.id:
        raise HTTPException(
            status_code=409,
            detail={"error": "resource_locked", "locked_by": existing.locked_by_email},
        )

    # resource_locks.expires_at is a naive (UTC) timestamp; the API may
    # deliver a tz-aware datetime (ISO with offset), which asyncpg rejects.
    if expires_at is not None and expires_at.tzinfo is not None:
        expires_at = expires_at.astimezone(UTC).replace(tzinfo=None)

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


async def get_locks_batch(
    db: AsyncSession, resource_type: str, resource_ids: list[uuid.UUID]
) -> dict[uuid.UUID, LockInfo]:
    if not resource_ids:
        return {}
    result = await db.execute(
        select(ResourceLock, User.email)
        .join(User, User.id == ResourceLock.locked_by, isouter=True)
        .where(
            ResourceLock.resource_type == resource_type,
            ResourceLock.resource_id.in_(resource_ids),
            (ResourceLock.expires_at.is_(None)) | (ResourceLock.expires_at > _now()),
        )
    )
    by_id: dict[uuid.UUID, LockInfo] = {}
    for lock, email in result.all():
        by_id[lock.resource_id] = LockInfo(
            locked_by=lock.locked_by,
            locked_by_email=email or "",
            locked_at=lock.locked_at,
            expires_at=lock.expires_at,
            reason=lock.reason,
        )
    return by_id


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


async def list_active_locks(
    db: AsyncSession,
    *,
    resource_type: str | None = None,
    user_id: uuid.UUID | None = None,
) -> list[LockInfo]:
    query = (
        select(ResourceLock, User.email)
        .join(User, User.id == ResourceLock.locked_by, isouter=True)
        .where(
            (ResourceLock.expires_at.is_(None)) | (ResourceLock.expires_at > _now()),
        )
    )
    if user_id:
        query = query.where(ResourceLock.locked_by == user_id)
    if resource_type:
        query = query.where(ResourceLock.resource_type == resource_type)
    query = query.order_by(ResourceLock.locked_at.desc())

    result = await db.execute(query)
    rows = result.all()

    by_type: dict[str, list[uuid.UUID]] = {}
    for lock, _ in rows:
        by_type.setdefault(lock.resource_type, []).append(lock.resource_id)

    titles: dict[tuple[str, uuid.UUID], tuple[str | None, str | None]] = {}

    for r_type, model in (
        ("object", Object),
        ("entity", Entity),
        ("place", Place),
        ("occurrence", Occurrence),
        ("collection", Collection),
        ("storage_location", StorageLocation),
    ):
        if r_type in by_type:
            res = await db.execute(
                select(model.id, model.idno, model.metadata_).where(model.id.in_(by_type[r_type]))
            )
            for m_id, m_idno, m_md in res.all():
                t = _extract_title(m_md or {}) or m_idno or str(m_id)[:8]
                titles[(r_type, m_id)] = (t, m_idno)

    if "procedure" in by_type:
        res = await db.execute(
            select(Procedure.id, Procedure.idno, Procedure.reference_number, Procedure.metadata_).where(
                Procedure.id.in_(by_type["procedure"])
            )
        )
        for p_id, p_idno, p_ref, p_md in res.all():
            t = _extract_title(p_md or {}) or p_ref or p_idno or str(p_id)[:8]
            titles[("procedure", p_id)] = (t, p_ref or p_idno)

    return [
        LockInfo(
            locked_by=lock.locked_by,
            locked_by_email=email or "",
            locked_at=lock.locked_at,
            expires_at=lock.expires_at,
            reason=lock.reason,
            resource_type=lock.resource_type,
            resource_id=lock.resource_id,
            title=titles.get((lock.resource_type, lock.resource_id), (None, None))[0],
            idno=titles.get((lock.resource_type, lock.resource_id), (None, None))[1],
        )
        for lock, email in rows
    ]
