from __future__ import annotations

from typing import Any

from fastapi import HTTPException

PUBLIC_STATUSES = ("public", "published")


def apply_public_visibility(query: Any, model: Any, current_user: Any | None) -> Any:
    """Restrict anonymous record queries to statuses meant for public display."""
    if current_user is None:
        return query.where(model.status.in_(PUBLIC_STATUSES))
    return query


def ensure_publicly_visible(record: Any, current_user: Any | None, detail: str) -> None:
    if current_user is None and record.status not in PUBLIC_STATUSES:
        raise HTTPException(status_code=404, detail=detail)
