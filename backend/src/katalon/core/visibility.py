# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select

PUBLIC_STATUSES = ("public", "published")
_PORTAL_TOMBSTONE_MODE: ContextVar[bool] = ContextVar("portal_tombstone_mode", default=False)


@contextmanager
def portal_tombstone_scope() -> Iterator[None]:
    """Return 410 Gone for withdrawn public records even for signed-in portal staff."""
    token = _PORTAL_TOMBSTONE_MODE.set(True)
    try:
        yield
    finally:
        _PORTAL_TOMBSTONE_MODE.reset(token)


def gone_error() -> HTTPException:
    """410 for withdrawn records. `no-store`: browsers otherwise cache a 410 indefinitely,
    which would keep a restored record hidden."""
    return HTTPException(
        status_code=410,
        detail="Dieser Datensatz wurde zurückgezogen.",
        headers={"Cache-Control": "no-store"},
    )


def apply_public_visibility(query: Any, model: Any, current_user: Any | None) -> Any:
    """Restrict record queries to statuses meant for public display; always hides soft-deleted rows."""
    if hasattr(model, "deleted_at"):
        query = query.where(model.deleted_at.is_(None))
    if current_user is None and hasattr(model, "status"):
        query = query.where(model.status.in_(PUBLIC_STATUSES))
    return query


def ensure_publicly_visible(
    record: Any,
    current_user: Any | None,
    detail: str,
    *,
    tombstone_for_all: bool = False,
) -> None:
    status = getattr(record, "status", None)
    is_public = status is None or status in PUBLIC_STATUSES
    if getattr(record, "deleted_at", None) is not None:
        if is_public and (
            tombstone_for_all or _PORTAL_TOMBSTONE_MODE.get() or current_user is None
        ):
            raise gone_error()
        raise HTTPException(status_code=404, detail=detail)
    if current_user is None and not is_public:
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
