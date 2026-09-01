# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

PUBLIC_STATUSES = ("public", "published")


def apply_public_visibility(query: Any, model: Any, current_user: Any | None) -> Any:
    """Restrict record queries to statuses meant for public display; always hides soft-deleted rows."""
    if hasattr(model, "deleted_at"):
        query = query.where(model.deleted_at.is_(None))
    if current_user is None:
        query = query.where(model.status.in_(PUBLIC_STATUSES))
        return query
    return query


def ensure_publicly_visible(record: Any, current_user: Any | None, detail: str) -> None:
    if getattr(record, "deleted_at", None) is not None:
        if current_user is None:
            raise HTTPException(status_code=410, detail="Dieser Datensatz wurde gelöscht.")
        raise HTTPException(status_code=404, detail=detail)
    if current_user is None and record.status not in PUBLIC_STATUSES:
        raise HTTPException(status_code=404, detail=detail)
