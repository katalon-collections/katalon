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
    for key in ("title", "name", "display_name", "place_name", "label"):
        val = md.get(key)
        if not val:
            continue
        if isinstance(val, list) and val:
            first = val[0]
            return first.get("value", "") if isinstance(first, dict) else str(first)
        if isinstance(val, str):
            return val
    return ""


def _flatten_text(md: dict, searchable_fields: set[str] | None = None) -> str:
    """Return a single search_text string with all (or only searchable) metadata values concatenated.

    If searchable_fields is provided, only keys in that set are included.
    """
    parts: list[str] = []
    for key, val in md.items():
        if searchable_fields is not None and key not in searchable_fields:
            continue
        if isinstance(val, str):
            parts.append(val)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    parts.append(item.get("value", ""))
                elif isinstance(item, str):
                    parts.append(item)
    return " ".join(p for p in parts if p)


def _clean_metadata(md: dict) -> dict:
    """Remove empty-string keys that break Elasticsearch indexing."""
    return {k: v for k, v in md.items() if k}


def _build_doc(record_type: str, record: Any, rel_data: dict[str, list[str]] | None = None, searchable_fields: set[str] | None = None) -> dict[str, Any]:
    # The Python attribute is metadata_ (DB column name is metadata)
    md: dict = _clean_metadata(getattr(record, "metadata_", None) or {})

    title = _extract_title(md)
    if not title:
        title = getattr(record, "idno", None) or ""

    related_text = " ".join(
        name
        for key in ("related_entities", "related_places", "related_occurrences")
        for name in (rel_data or {}).get(key, [])
    )
    search_text = _flatten_text(md, searchable_fields)
    if related_text:
        search_text = f"{search_text} {related_text}".strip()

    doc: dict[str, Any] = {
        "record_type": record_type,
        "title": title,
        "status": getattr(record, "status", None),
        "metadata": md,
        "search_text": search_text,
        "created_at": record.created_at.isoformat() if getattr(record, "created_at", None) else None,
        "updated_at": record.updated_at.isoformat() if getattr(record, "updated_at", None) else None,
    }
    if rel_data:
        doc.update(rel_data)
    return doc


async def _load_relation_titles(record_type: str, record_id: UUID, db: Any) -> dict[str, list[str]]:
    """Return names of related entities/places/occurrences for denormalisation in ES."""
    from sqlalchemy import or_, and_, select
    from katalon.core.models import Relation, Entity, Place, Occurrence

    TYPE_MAP: dict[str, tuple[str, Any]] = {
        "entity":     ("related_entities", Entity),
        "place":      ("related_places", Place),
        "occurrence": ("related_occurrences", Occurrence),
    }
    related: dict[str, list[str]] = {k: [] for k, _ in TYPE_MAP.values()}

    stmt = select(Relation).where(
        or_(
            and_(Relation.from_type == record_type, Relation.from_id == record_id),
            and_(Relation.to_type == record_type, Relation.to_id == record_id),
        )
    )
    result = await db.execute(stmt)
    relations = result.scalars().all()

    for rel in relations:
        if rel.from_type == record_type and rel.from_id == record_id:
            other_type, other_id = rel.to_type, rel.to_id
        else:
            other_type, other_id = rel.from_type, rel.from_id

        mapping = TYPE_MAP.get(other_type)
        if not mapping:
            continue
        field_name, model = mapping
        rec = await db.get(model, other_id)
        if rec:
            title = _extract_title(rec.metadata_ or {})
            if title:
                related[field_name].append(title)

    return related


async def index_record(record_type: str, record: Any, db: Any = None) -> None:
    from sqlalchemy import select
    from katalon.core.models import FieldDefinition

    rel_data: dict[str, list[str]] | None = None
    if db is not None and record_type == "object":
        rel_data = await _load_relation_titles(record_type, record.id, db)

    searchable_fields: set[str] | None = None
    if db is not None:
        result = await db.execute(
            select(FieldDefinition.name).where(
                FieldDefinition.target_type == record_type,
                FieldDefinition.is_searchable.is_(True),
                FieldDefinition.is_deleted.is_(False),
            )
        )
        names = result.scalars().all()
        if names:
            searchable_fields = set(names)

    doc = _build_doc(record_type, record, rel_data, searchable_fields)
    await index_document(str(record.id), doc)


async def remove_record(record_id: UUID) -> None:
    await delete_document(str(record_id))


async def search(
    query: str | None = None,
    record_type: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    extra_filters: dict[str, str] | None = None,
    facet_fields: list[str] | None = None,
    rel_filters: dict[str, str] | None = None,
) -> dict[str, Any]:
    from_ = (page - 1) * page_size
    raw = await search_documents(
        query, record_type, status, from_, page_size,
        extra_filters=extra_filters,
        facet_fields=facet_fields,
        rel_filters=rel_filters,
    )

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
