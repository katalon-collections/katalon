# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

from typing import Any, Literal

SORTABLE_COLUMNS = ("idno", "status", "updated_at")

SortBy = Literal["idno", "status", "updated_at"]
SortDir = Literal["asc", "desc"]


def apply_sort(query: Any, model: Any, sort_by: SortBy | None, sort_dir: SortDir) -> Any:
    """Order a list query by a whitelisted column; falls back to updated_at desc."""
    column = getattr(model, sort_by, None) if sort_by in SORTABLE_COLUMNS else None
    if column is None:
        return query.order_by(model.updated_at.desc())
    return query.order_by(column.asc() if sort_dir == "asc" else column.desc())
