from __future__ import annotations

from typing import Any
from uuid import UUID

from katalon.integrations.elasticsearch import (
    delete_document,
    index_document,
    search_documents,
)


def _extract_title(md: dict) -> str:
    """Extract a display title from metadata, handling both plain strings and repeatable-field lists."""
    for key in ("title", "name", "label"):
        val = md.get(key)
        if not val:
            continue
        if isinstance(val, list) and val:
            first = val[0]
            return first.get("value", "") if isinstance(first, dict) else str(first)
        if isinstance(val, str):
            return val
    return ""


def _flatten_text(md: dict) -> str:
    """Return a single search_text string with all metadata values concatenated."""
    parts: list[str] = []
    for val in md.values():
        if isinstance(val, str):
            parts.append(val)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    parts.append(item.get("value", ""))
                elif isinstance(item, str):
                    parts.append(item)
    return " ".join(p for p in parts if p)


def _build_doc(record_type: str, record: Any) -> dict[str, Any]:
    # The Python attribute is metadata_ (DB column name is metadata)
    md: dict = getattr(record, "metadata_", None) or {}

    title = _extract_title(md)
    if not title:
        title = getattr(record, "idno", None) or ""

    return {
        "record_type": record_type,
        "title": title,
        "status": getattr(record, "status", None),
        "metadata": md,
        "search_text": _flatten_text(md),
        "created_at": record.created_at.isoformat() if getattr(record, "created_at", None) else None,
        "updated_at": record.updated_at.isoformat() if getattr(record, "updated_at", None) else None,
    }


async def index_record(record_type: str, record: Any) -> None:
    doc = _build_doc(record_type, record)
    await index_document(str(record.id), doc)


async def remove_record(record_id: UUID) -> None:
    await delete_document(str(record_id))


async def search(
    query: str | None = None,
    record_type: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    from_ = (page - 1) * page_size
    raw = await search_documents(query, record_type, status, from_, page_size)

    hits = raw.get("hits", {})
    total = hits.get("total", {}).get("value", 0)
    items = [
        {
            "id": h["_id"],
            "score": h.get("_score"),
            **h["_source"],
        }
        for h in hits.get("hits", [])
    ]

    aggs = raw.get("aggregations", {})
    facets: dict[str, list[dict]] = {}
    for agg_key, agg_val in aggs.items():
        facets[agg_key] = [
            {"value": b["key"], "count": b["doc_count"]}
            for b in agg_val.get("buckets", [])
        ]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
        "facets": facets,
    }
