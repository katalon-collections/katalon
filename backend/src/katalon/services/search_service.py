from __future__ import annotations

from typing import Any
from uuid import UUID

from katalon.integrations.elasticsearch import (
    delete_document,
    index_document,
    search_documents,
)


def _build_doc(record_type: str, record: Any) -> dict[str, Any]:
    title = ""
    metadata: dict = {}

    if hasattr(record, "metadata") and record.metadata:
        md = record.metadata
        title_field = md.get("title") or md.get("name") or md.get("label")
        if isinstance(title_field, list) and title_field:
            title = title_field[0].get("value", "") if isinstance(title_field[0], dict) else str(title_field[0])
        elif isinstance(title_field, str):
            title = title_field
        metadata = md

    if not title and hasattr(record, "identifier"):
        title = record.identifier or ""

    return {
        "record_type": record_type,
        "title": title,
        "status": getattr(record, "status", None),
        "metadata": metadata,
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
