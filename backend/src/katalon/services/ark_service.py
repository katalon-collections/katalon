# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.visibility import PUBLIC_STATUSES
from katalon.services.pid_service import record_portal_url

_PUBLIC_TABLES = (
    ("object", "objects"),
    ("entity", "entities"),
    ("place", "places"),
    ("occurrence", "occurrences"),
)


async def resolve_ark(db: AsyncSession, ark: str) -> str | None:
    """Resolve one stored ARK of a public (or withdrawn public) record to its canonical portal URL.

    Soft-deleted records that were public still resolve so callers follow the redirect
    to the portal detail route and receive the 410 tombstone page. Never-public drafts
    remain excluded and resolve to None (404).
    """
    statuses = tuple(PUBLIC_STATUSES)
    for record_type, table in _PUBLIC_TABLES:
        result = await db.execute(
            text(
                f"SELECT id FROM {table} "  # noqa: S608
                f"WHERE (status = ANY(:statuses) OR EXISTS ("
                f"SELECT 1 FROM oai_record_states s WHERE s.record_type = :record_type AND s.record_id = {table}.id)) "
                f"AND jsonb_path_exists(metadata, '$.**.value ? (@ == $ark)', jsonb_build_object('ark', CAST(:ark AS text))) "
                f"ORDER BY deleted_at NULLS FIRST "
                f"LIMIT 1"
            ),
            {
                "statuses": statuses,
                "record_type": record_type,
                "ark": ark,
            },
        )
        record_id = result.scalar_one_or_none()
        if record_id is not None:
            return record_portal_url(record_type, record_id)
    return None
