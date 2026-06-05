from __future__ import annotations

from typing import Any
from uuid import UUID

from katalon.integrations.elasticsearch import search_documents


def _extract_title(md: dict) -> str:
    """Extract a display title from metadata, handling both plain strings and repeatable-field lists.

    Checks common title field names in both English and German.
    """
    for key in ("label", "title", "titel", "name", "display_name", "place_name", "bezeichnung"):
        val = md.get(key)
        if not val:
            continue
        if isinstance(val, list) and val:
            first = val[0]
            return first.get("value", "") if isinstance(first, dict) else str(first)
        if isinstance(val, str):
            return val
    return ""


def _extract_display_value(val: Any) -> str | None:
    """Extract a human-readable string from a single metadata item.

    Handles repeatable plain fields {"value": "..."}, vocab {"id": ..., "label": "..."},
    and authority {"id": "Q762", "label": "Name"} field formats.
    """
    if isinstance(val, dict):
        return str(val["label"]) if "label" in val else (str(val["value"]) if "value" in val else None)
    if val is not None:
        return str(val)
    return None


def _extract_facet_value(val: Any) -> str | list[str] | None:
    """Extract keyword-safe facet value(s) from a metadata field value.

    Returns a string or list of strings suitable for ES keyword faceting.
    """
    if isinstance(val, list):
        results = [_extract_display_value(item) for item in val]
        flat = [r for r in results if r]
        if not flat:
            return None
        return flat if len(flat) > 1 else flat[0]
    return _extract_display_value(val)


_KNOWN_ENTRY_KEYS = {"label", "value", "id", "source", "external_id"}


def _is_group_instance(d: dict) -> bool:
    """Return True if a dict looks like a group field instance (not a vocab/authority/pid entry)."""
    return not bool(_KNOWN_ENTRY_KEYS & d.keys())


def _flatten_text(md: dict, searchable_fields: set[str] | None = None) -> str:
    """Return a single search_text string with all (or only searchable) metadata values concatenated.

    If searchable_fields is provided, only keys in that set are included.
    Group field instances (arrays of sub-field dicts) are recursively flattened.
    """
    parts: list[str] = []
    for key, val in md.items():
        if searchable_fields is not None and key not in searchable_fields:
            continue
        if isinstance(val, str):
            parts.append(val)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, dict) and _is_group_instance(item):
                    # Group instance: extract all sub-field values
                    for sv in item.values():
                        parts.append(_extract_display_value(sv) or "")
                else:
                    parts.append(_extract_display_value(item) or "")
        elif isinstance(val, dict):
            parts.append(_extract_display_value(val) or "")
    return " ".join(p for p in parts if p)


def _clean_metadata(md: dict) -> dict:
    """Remove empty-string keys that break Elasticsearch indexing."""
    return {k: v for k, v in md.items() if k}


def _normalize_for_index(val: Any) -> Any:
    """Normalize metadata values for ES indexing.

    Repeatable fields are stored as [{value: "..."}] in the DB.
    For ES we flatten them to a list of strings so the mapping stays consistent.
    Numbers are also converted to strings for keyword facet fields.
    """
    if isinstance(val, list) and val:
        result: list[str] = []
        for item in val:
            if isinstance(item, dict):
                v = item.get("value")
                if v is not None:
                    result.append(str(v))
            elif isinstance(item, str):
                result.append(item)
            else:
                result.append(str(item))
        return result if len(result) > 1 else (result[0] if result else "")
    if isinstance(val, dict):
        return {k: _normalize_for_index(v) for k, v in val.items()}
    if isinstance(val, (int, float)):
        return str(val)
    return val


def _build_doc(
    record_type: str,
    record: Any,
    rel_data: dict[str, list[str]] | None = None,
    searchable_fields: set[str] | None = None,
    facet_fields: set[str] | None = None,
    group_fields: set[str] | None = None,
) -> dict[str, Any]:
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

    # Normalize metadata for ES: flatten repeatable fields to strings
    indexed_metadata = {k: _normalize_for_index(v) for k, v in md.items()}

    doc: dict[str, Any] = {
        "record_type": record_type,
        "title": title,
        "status": getattr(record, "status", None),
        "metadata": indexed_metadata,
        "search_text": search_text,
        "created_at": record.created_at.isoformat() if getattr(record, "created_at", None) else None,
        "updated_at": record.updated_at.isoformat() if getattr(record, "updated_at", None) else None,
    }

    # Build facet_* fields for fields marked as is_facet
    if facet_fields:
        for field_name in facet_fields:
            val = md.get(field_name)
            if val is None:
                continue
            label = _extract_facet_value(val)
            if label:
                doc[f"facet_{field_name}"] = label

    # Index group field instances as nested ES objects under grp_* keys
    if group_fields:
        for field_name in group_fields:
            val = md.get(field_name)
            if isinstance(val, list) and val:
                doc[f"grp_{field_name}"] = val

    if rel_data:
        doc.update(rel_data)
    return doc


async def _load_relation_titles(record_type: str, record_id: UUID, db: Any) -> dict[str, list[str]]:
    """Return names of related entities/places/occurrences for denormalisation in ES."""
    from sqlalchemy import and_, or_, select

    from katalon.core.models import Entity, Occurrence, Place, Relation

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


async def build_index_doc(record_type: str, record: Any, db: Any = None) -> dict[str, Any]:
    """Build the ES document for a record without writing to ES."""
    from sqlalchemy import select

    from katalon.core.models import FieldDefinition

    rel_data: dict[str, list[str]] | None = None
    if db is not None and record_type == "object":
        rel_data = await _load_relation_titles(record_type, record.id, db)

    searchable_fields: set[str] | None = None
    facet_fields: set[str] | None = None
    group_fields: set[str] | None = None
    if db is not None:
        result = await db.execute(
            select(
                FieldDefinition.name,
                FieldDefinition.is_searchable,
                FieldDefinition.is_facet,
                FieldDefinition.field_type,
            ).where(
                FieldDefinition.target_type == record_type,
                FieldDefinition.is_deleted.is_(False),
                FieldDefinition.parent_id.is_(None),
            )
        )
        rows = result.all()
        searchable_fields = {r.name for r in rows if r.is_searchable}
        facet_fields = {r.name for r in rows if r.is_facet}
        group_fields = {r.name for r in rows if r.field_type == "group"}

    return _build_doc(record_type, record, rel_data, searchable_fields, facet_fields, group_fields)


async def index_record(record_type: str, record: Any, db: Any = None) -> None:
    """Build ES document and dispatch Celery task for indexed write with retry."""
    from katalon.workers.index_tasks import index_record_task

    doc = await build_index_doc(record_type, record, db)
    index_record_task.delay(record_type, str(record.id), doc)


async def remove_record(record_id: UUID) -> None:
    from katalon.workers.index_tasks import remove_record_task

    remove_record_task.delay(str(record_id))


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
