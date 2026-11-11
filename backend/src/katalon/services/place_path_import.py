# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Place paths in imports: ``Deutschland>Mecklenburg-Vorpommern>Schwerin`` becomes a place chain.

The separator is explicit (``path_separator`` on the mapping entry of the ``label``
target); nothing is guessed. The last segment is the place, the segments before it
are its ancestors. Missing ancestors are created as places of their own.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import Place


def place_path_separator(mapping: dict[str, Any]) -> str | None:
    """Separator configured on the mapping entry that feeds the place ``label``."""
    for entry in mapping.values():
        if isinstance(entry, dict) and entry.get("target") == "label":
            sep = entry.get("path_separator")
            if isinstance(sep, str) and sep.strip():
                return sep.strip()
    return None


def split_path(value: str, separator: str) -> list[str]:
    """Split a path into trimmed segments. Raises ``ValueError`` for empty segments."""
    segments = [part.strip() for part in value.split(separator)]
    if any(not part for part in segments):
        raise ValueError(f"Ortspfad '{value}' enthält ein leeres Element.")
    return segments


async def ensure_ancestors(
    session: AsyncSession,
    ancestors: list[str],
    separator: str,
    cache: dict[tuple[uuid.UUID | None, str], uuid.UUID],
    created: list[Place],
) -> uuid.UUID | None:
    """Find or create the chain ``ancestors`` (root first); return the innermost place id.

    A level is found by label under its parent. A new level gets its own path as ID number
    (e.g. ``Deutschland>Mecklenburg-Vorpommern``) and is appended to ``created``.
    """
    parent_id: uuid.UUID | None = None
    for depth, label in enumerate(ancestors):
        key = (parent_id, label)
        if key not in cache:
            query = select(Place.id).where(
                Place.deleted_at.is_(None), Place.metadata_["label"].astext == label
            )
            query = query.where(
                Place.parent_id == parent_id if parent_id else Place.parent_id.is_(None)
            )
            found = (await session.execute(query.limit(1))).scalar_one_or_none()
            if found is None:
                path_idno = separator.join(ancestors[: depth + 1])
                place = Place(
                    idno=path_idno,
                    parent_id=parent_id,
                    status="draft",
                    metadata_={"label": label},
                )
                session.add(place)
                await session.flush()
                created.append(place)
                found = place.id
            cache[key] = found
        parent_id = cache[key]
    return parent_id
