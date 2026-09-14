# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select

PUBLIC_STATUSES = ("public", "published")


def apply_public_visibility(query: Any, model: Any, current_user: Any | None) -> Any:
    """Restrict record queries to statuses meant for public display; always hides soft-deleted rows."""
    if hasattr(model, "deleted_at"):
        query = query.where(model.deleted_at.is_(None))
    if current_user is None and hasattr(model, "status"):
        query = query.where(model.status.in_(PUBLIC_STATUSES))
    return query


def ensure_publicly_visible(record: Any, current_user: Any | None, detail: str) -> None:
    if getattr(record, "deleted_at", None) is not None:
        if current_user is None:
            raise HTTPException(status_code=410, detail="Dieser Datensatz wurde gelöscht.")
        raise HTTPException(status_code=404, detail=detail)
    status = getattr(record, "status", None)
    if current_user is None and status is not None and status not in PUBLIC_STATUSES:
        raise HTTPException(status_code=404, detail=detail)


#: Core record types that carry a `status` field and appear in search
#: (excludes the schema-only `vocabulary_term` target type).
SEARCHABLE_RECORD_TYPES = (
    "object", "entity", "place", "occurrence", "procedure", "collection", "storage_location",
)


async def readable_record_types(db: Any, user: Any | None) -> tuple[str, ...] | None:
    """Return the record types `user` may see beyond public/published statuses.

    Mirrors `has_record_permission()`'s per-type `read` check, but batched for
    use by the cross-type search endpoints. `None` means unrestricted (no
    logged-in user is ever unrestricted; only admin/superuser are) — callers
    must still restrict every other type to `PUBLIC_STATUSES`. An empty tuple
    means the user has no elevated read access anywhere.
    """
    if user is None:
        return ()
    if user.role in {"admin", "superuser"}:
        return None
    from katalon.core.models import RolePermission

    result = await db.execute(
        select(RolePermission.record_type).where(
            RolePermission.role == user.role,
            RolePermission.action == "read",
            RolePermission.record_type.in_(SEARCHABLE_RECORD_TYPES),
        )
    )
    types = set(result.scalars().all())
    if user.role == "viewer":
        # Special-cased in has_record_permission(): viewer never reads these,
        # even if a stray role_permissions row grants it.
        types -= {"procedure", "storage_location"}
    return tuple(types)
