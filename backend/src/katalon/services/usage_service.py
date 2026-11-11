# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Anonymous per-day view/download counters (no IP, cookie or session stored)."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import AdminConfig, RecordUsageDaily

UsageKind = Literal["views", "downloads"]

# Crawlers mostly never run the portal's JS beacon (nginx sends them to the SEO
# page); this catches the ones that fetch downloads or the beacon directly.
_BOT_RE = re.compile(
    r"bot|crawl|spider|slurp|archiver|facebookexternalhit|headless|curl|wget|python|httpx",
    re.IGNORECASE,
)


def is_bot(user_agent: str | None) -> bool:
    return not user_agent or bool(_BOT_RE.search(user_agent))


async def usage_stats_enabled(db: AsyncSession) -> bool:
    enabled = await db.scalar(
        select(AdminConfig.usage_stats_enabled).where(AdminConfig.key == "default")
    )
    return True if enabled is None else bool(enabled)


async def count(
    db: AsyncSession, record_type: str, record_id: uuid.UUID, kind: UsageKind
) -> None:
    """Increment today's counter atomically (safe across API workers)."""
    column = getattr(RecordUsageDaily, kind)
    stmt = insert(RecordUsageDaily).values(
        record_type=record_type,
        record_id=record_id,
        day=datetime.now(UTC).date(),
        **{kind: 1},
    )
    await db.execute(
        stmt.on_conflict_do_update(
            index_elements=["record_type", "record_id", "day"],
            set_={kind: column + 1},
        )
    )


async def totals(
    db: AsyncSession, record_type: str, record_id: uuid.UUID
) -> dict[str, int]:
    """All-time and last-30-days sums of views and downloads."""
    since = datetime.now(UTC).date() - timedelta(days=29)
    recent = RecordUsageDaily.day >= since

    views, downloads = RecordUsageDaily.views, RecordUsageDaily.downloads
    row = (
        await db.execute(
            select(
                func.coalesce(func.sum(views), 0),
                func.coalesce(func.sum(downloads), 0),
                func.coalesce(func.sum(views).filter(recent), 0),
                func.coalesce(func.sum(downloads).filter(recent), 0),
            ).where(
                RecordUsageDaily.record_type == record_type,
                RecordUsageDaily.record_id == record_id,
            )
        )
    ).one()
    return {
        "views": int(row[0]),
        "downloads": int(row[1]),
        "views_30d": int(row[2]),
        "downloads_30d": int(row[3]),
    }
