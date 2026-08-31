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
    """Resolve one public stored ARK to its canonical portal URL."""
    statuses = tuple(PUBLIC_STATUSES)
    for record_type, table in _PUBLIC_TABLES:
        result = await db.execute(
            text(
                f"SELECT id FROM {table} "  # noqa: S608
                f"WHERE status = ANY(:statuses) AND deleted_at IS NULL "
                f"AND jsonb_path_exists(metadata, '$.**.value ? (@ == $ark)', jsonb_build_object('ark', CAST(:ark AS text))) "
                f"LIMIT 1"
            ),
            {
                "statuses": statuses,
                "ark": ark,
            },
        )
        record_id = result.scalar_one_or_none()
        if record_id is not None:
            return record_portal_url(record_type, record_id)
    return None
