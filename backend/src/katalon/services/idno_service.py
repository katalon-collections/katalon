"""
IDNO schema service: format generation, atomic counter management, pattern validation.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_TYPE_ABBREV: dict[str, str] = {
    "object": "obj",
    "entity": "ent",
    "place": "pla",
    "occurrence": "occ",
}

# Matches {counter}, {counter:05d}, {year}, {type}
_PLACEHOLDER_RE = re.compile(r"\{counter(?::([^}]+))?\}|\{year\}|\{type\}")


def format_idno(schema: str, counter: int, record_type: str, year: int | None = None) -> str:
    """Render a schema string with the given counter and current year."""
    if year is None:
        year = datetime.now(UTC).year
    abbrev = _TYPE_ABBREV.get(record_type, record_type[:3])

    def _replace(m: re.Match) -> str:  # type: ignore[type-arg]
        full = m.group(0)
        if full == "{year}":
            return str(year)
        if full == "{type}":
            return abbrev
        fmt_spec = m.group(1)
        if fmt_spec:
            return format(counter, fmt_spec)
        return str(counter)

    return _PLACEHOLDER_RE.sub(_replace, schema)


async def _current_counter(db: AsyncSession, record_type: str) -> int:
    result = await db.execute(
        text("SELECT current_value FROM idno_counters WHERE record_type = :rt"),
        {"rt": record_type},
    )
    row = result.fetchone()
    return int(row[0]) if row else 0


async def peek_next_idno(db: AsyncSession, record_type: str, schema: str) -> str:
    """Return the next formatted idno WITHOUT modifying the counter (preview only)."""
    current = await _current_counter(db, record_type)
    return format_idno(schema, current + 1, record_type)


async def consume_next_idno(db: AsyncSession, record_type: str, schema: str) -> str:
    """Atomically increment the counter and return the newly formatted idno."""
    result = await db.execute(
        text(
            "INSERT INTO idno_counters (record_type, current_value) VALUES (:rt, 1) "
            "ON CONFLICT (record_type) DO UPDATE "
            "SET current_value = idno_counters.current_value + 1 "
            "RETURNING current_value"
        ),
        {"rt": record_type},
    )
    new_value = int(result.scalar_one())
    return format_idno(schema, new_value, record_type)


async def maybe_advance_counter(
    db: AsyncSession, record_type: str, schema: str, idno: str
) -> None:
    """Increment the counter if the provided idno matches the next auto-generated value.

    This prevents gaps when a user accepts the suggested idno verbatim, while
    leaving the counter untouched when they type a custom value.
    """
    current = await _current_counter(db, record_type)
    expected = format_idno(schema, current + 1, record_type)
    if idno == expected:
        await db.execute(
            text(
                "INSERT INTO idno_counters (record_type, current_value) VALUES (:rt, 1) "
                "ON CONFLICT (record_type) DO UPDATE "
                "SET current_value = idno_counters.current_value + 1"
            ),
            {"rt": record_type},
        )


def validate_idno_pattern(pattern: str, idno: str) -> bool:
    """Return True if idno matches the configured regex pattern.

    Returns True on invalid regex to avoid blocking saves due to misconfiguration.
    """
    try:
        return bool(re.fullmatch(pattern, idno))
    except re.error:
        return True
