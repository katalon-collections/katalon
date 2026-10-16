# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Which records OAI-PMH has to report as deleted.

A row in ``oai_record_states`` means "this record was public at some point".
``deleted_at`` marks that it no longer is (depublished or deleted). Harvesters
with incremental harvesting only learn about such removals from a
deleted header; without it the record stays in their portal until a full harvest.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, time
from typing import Any

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import OaiRecordState
from katalon.core.visibility import PUBLIC_STATUSES

# Record types OAI-PMH can disseminate at all.
TRACKED_TYPES = frozenset({"object", "entity", "place", "occurrence", "collection"})


@dataclass(frozen=True)
class DeletedRecord:
    record_type: str
    record_id: str
    deleted_at: datetime


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _as_uuid(value: Any) -> uuid.UUID | None:
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


async def mark_public(db: AsyncSession, record_type: str, record_id: Any) -> None:
    """Record is (again) disseminated: create the row or clear its deleted_at."""
    rid = _as_uuid(record_id)
    if record_type not in TRACKED_TYPES or rid is None:
        return
    stmt = insert(OaiRecordState).values(record_type=record_type, record_id=rid, deleted_at=None)
    await db.execute(
        stmt.on_conflict_do_update(
            index_elements=[OaiRecordState.record_type, OaiRecordState.record_id],
            set_={"deleted_at": None},
        )
    )


async def mark_withdrawn(db: AsyncSession, record_type: str | None, record_id: Any) -> None:
    """Record left dissemination. Only records that were public before get a deleted_at."""
    rid = _as_uuid(record_id)
    if rid is None or (record_type is not None and record_type not in TRACKED_TYPES):
        return
    conditions = [OaiRecordState.record_id == rid, OaiRecordState.deleted_at.is_(None)]
    if record_type is not None:
        conditions.append(OaiRecordState.record_type == record_type)
    await db.execute(update(OaiRecordState).where(*conditions).values(deleted_at=_now()))


async def track(db: AsyncSession, record_type: str, record: Any) -> None:
    """Sync the state for a record that is being (re)indexed."""
    public = getattr(record, "status", None) in PUBLIC_STATUSES and getattr(
        record, "deleted_at", None
    ) is None
    if public:
        await mark_public(db, record_type, record.id)
    else:
        await mark_withdrawn(db, record_type, record.id)


def parse_oai_date(value: str | None, *, end: bool = False) -> datetime | None:
    """OAI-PMH from/until (YYYY-MM-DD or YYYY-MM-DDThh:mm:ssZ) as naive UTC."""
    if not value:
        return None
    text = value.strip().removesuffix("Z")
    try:
        if "T" in text:
            return datetime.fromisoformat(text).replace(tzinfo=None)
        day = datetime.fromisoformat(text).date()
    except ValueError:
        return None
    return datetime.combine(day, time.max if end else time.min)


def _filters(
    record_types: set[str], from_: str | None, until: str | None
) -> list[Any]:
    conditions: list[Any] = [
        OaiRecordState.deleted_at.is_not(None),
        OaiRecordState.record_type.in_(sorted(record_types & TRACKED_TYPES)),
    ]
    if (start := parse_oai_date(from_)) is not None:
        conditions.append(OaiRecordState.deleted_at >= start)
    if (stop := parse_oai_date(until, end=True)) is not None:
        conditions.append(OaiRecordState.deleted_at <= stop)
    return conditions


async def count_deleted(
    db: AsyncSession, record_types: set[str], from_: str | None, until: str | None
) -> int:
    if not record_types & TRACKED_TYPES:
        return 0
    stmt = select(func.count()).select_from(OaiRecordState).where(*_filters(record_types, from_, until))
    return int((await db.execute(stmt)).scalar_one())


async def deleted_page(
    db: AsyncSession,
    record_types: set[str],
    from_: str | None,
    until: str | None,
    after: list[str] | None,
    limit: int,
) -> list[DeletedRecord]:
    """Deleted records ordered by (deleted_at, record_id); ``after`` is the last key seen."""
    if not record_types & TRACKED_TYPES:
        return []
    conditions = _filters(record_types, from_, until)
    if after:
        last_at = datetime.fromisoformat(after[0])
        last_id = uuid.UUID(after[1])
        conditions.append(
            or_(
                OaiRecordState.deleted_at > last_at,
                and_(OaiRecordState.deleted_at == last_at, OaiRecordState.record_id > last_id),
            )
        )
    stmt = (
        select(OaiRecordState)
        .where(*conditions)
        .order_by(OaiRecordState.deleted_at, OaiRecordState.record_id)
        .limit(limit)
    )
    return [
        DeletedRecord(row.record_type, str(row.record_id), row.deleted_at)
        for row in (await db.execute(stmt)).scalars()
        if row.deleted_at is not None
    ]


async def get_deleted(db: AsyncSession, record_type: str, record_id: str) -> DeletedRecord | None:
    rid = _as_uuid(record_id)
    if rid is None:
        return None
    row = await db.get(OaiRecordState, (record_type, rid))
    if row is None or row.deleted_at is None:
        return None
    return DeletedRecord(row.record_type, str(row.record_id), row.deleted_at)
