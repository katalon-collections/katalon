# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Presence Lock: shows who else is currently editing a record.

A client heartbeats every ~20s while the edit form is open; a row older than
ACTIVE_WINDOW_SECONDS counts as expired (no cleanup worker needed, stale rows
are just filtered out and get overwritten by the next heartbeat elsewhere).
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import AdminConfig, EditPresence, User

ACTIVE_WINDOW_SECONDS = 60


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _cutoff() -> datetime:
    return _now() - timedelta(seconds=ACTIVE_WINDOW_SECONDS)


@dataclass
class ActivePresence:
    user_id: uuid.UUID
    user_email: str
    since: datetime


async def _get_lock_mode(db: AsyncSession) -> str:
    config = await db.scalar(select(AdminConfig).where(AdminConfig.key == "default"))
    return config.presence_lock_mode if config else "warning"


async def heartbeat(
    db: AsyncSession, resource_type: str, resource_id: uuid.UUID, user_id: uuid.UUID, session_id: str
) -> None:
    stmt = pg_insert(EditPresence).values(
        id=uuid.uuid4(),
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=user_id,
        session_id=session_id,
        last_seen_at=_now(),
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_edit_presence_session",
        set_={"last_seen_at": _now(), "user_id": user_id},
    )
    await db.execute(stmt)
    await db.flush()


async def release(
    db: AsyncSession, resource_type: str, resource_id: uuid.UUID, session_id: str
) -> None:
    await db.execute(
        delete(EditPresence).where(
            EditPresence.resource_type == resource_type,
            EditPresence.resource_id == resource_id,
            EditPresence.session_id == session_id,
        )
    )
    await db.flush()


async def get_active_presences(
    db: AsyncSession, resource_type: str, resource_id: uuid.UUID, *, exclude_user_id: uuid.UUID | None = None
) -> list[ActivePresence]:
    query = (
        select(EditPresence, User.email)
        .join(User, User.id == EditPresence.user_id)
        .where(
            EditPresence.resource_type == resource_type,
            EditPresence.resource_id == resource_id,
            EditPresence.last_seen_at >= _cutoff(),
        )
    )
    if exclude_user_id is not None:
        query = query.where(EditPresence.user_id != exclude_user_id)
    result = await db.execute(query)
    seen: dict[uuid.UUID, ActivePresence] = {}
    for presence, email in result.all():
        existing = seen.get(presence.user_id)
        if existing is None or presence.last_seen_at > existing.since:
            seen[presence.user_id] = ActivePresence(
                user_id=presence.user_id, user_email=email, since=presence.last_seen_at
            )
    return list(seen.values())


async def get_active_presences_batch(
    db: AsyncSession, resource_type: str, resource_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[ActivePresence]]:
    if not resource_ids:
        return {}
    result = await db.execute(
        select(EditPresence, User.email)
        .join(User, User.id == EditPresence.user_id)
        .where(
            EditPresence.resource_type == resource_type,
            EditPresence.resource_id.in_(resource_ids),
            EditPresence.last_seen_at >= _cutoff(),
        )
    )
    by_resource: dict[uuid.UUID, dict[uuid.UUID, ActivePresence]] = {}
    for presence, email in result.all():
        bucket = by_resource.setdefault(presence.resource_id, {})
        existing = bucket.get(presence.user_id)
        if existing is None or presence.last_seen_at > existing.since:
            bucket[presence.user_id] = ActivePresence(
                user_id=presence.user_id, user_email=email, since=presence.last_seen_at
            )
    return {resource_id: list(users.values()) for resource_id, users in by_resource.items()}


async def enforce_not_blocked(
    db: AsyncSession, resource_type: str, resource_id: uuid.UUID, current_user: User
) -> None:
    """Raise 409 if presence_lock_mode is 'blocking' and another user holds the record."""
    if await _get_lock_mode(db) != "blocking":
        return
    others = await get_active_presences(db, resource_type, resource_id, exclude_user_id=current_user.id)
    if others:
        raise HTTPException(
            status_code=409,
            detail={"error": "presence_locked", "locked_by": others[0].user_email},
        )
