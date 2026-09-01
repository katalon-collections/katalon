# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy import Text, cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import (
    AuthoritySource,
    Banner,
    FieldDefinition,
    FormVariant,
    OAISet,
    RecordSubtype,
    StaticPage,
    User,
    Vocabulary,
    VocabularyTerm,
)
from katalon.integrations.elasticsearch import search_documents


def _is_leap_year(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def _date_part_bounds(value: str) -> tuple[int, int]:
    value = value.removesuffix("~?").removesuffix("~").removesuffix("?")
    match = re.fullmatch(r"(-?\d{4})(?:-(\d{2})(?:-(\d{2}))?)?", value)
    if not match:
        raise ValueError(f"Ungültiges Datum: {value}")
    year = int(match.group(1))
    month = int(match.group(2)) if match.group(2) else None
    day = int(match.group(3)) if match.group(3) else None
    if month is not None and not 1 <= month <= 12:
        raise ValueError(f"Ungültiger Monat: {value}")
    if day is not None and month is not None:
        days = [31, 29 if _is_leap_year(year) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        if not 1 <= day <= days[month - 1]:
            raise ValueError(f"Ungültiger Tag: {value}")
        encoded = year * 10000 + month * 100 + day
        return encoded, encoded
    if month is not None:
        days = [31, 29 if _is_leap_year(year) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        return year * 10000 + month * 100 + 1, year * 10000 + month * 100 + days[month - 1]
    return year * 10000 + 101, year * 10000 + 1231


def date_bounds(value: str) -> tuple[int | None, int | None]:
    """Convert one EDTF-lite value into sortable inclusive bounds."""
    if value.count("/") == 1:
        start, end = value.split("/", 1)
        lower = _date_part_bounds(start)[0] if start else None
        upper = _date_part_bounds(end)[1] if end else None
        if lower is not None and upper is not None and lower > upper:
            raise ValueError(f"Ungültiger Datumsbereich: {value}")
        return lower, upper
    lower, upper = _date_part_bounds(value)
    return lower, upper


def _extract_title(md: dict[str, Any]) -> str:
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


def _is_group_instance(d: dict[str, Any]) -> bool:
    """Return True if a dict looks like a group field instance (not a vocab/authority/pid entry)."""
    return not bool(_KNOWN_ENTRY_KEYS & d.keys())


def _flatten_text(md: dict[str, Any], searchable_fields: set[str] | None = None) -> str:
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


def _clean_metadata(md: dict[str, Any]) -> dict[str, Any]:
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


def _advanced_scalar_values(value: Any) -> list[Any]:
    if isinstance(value, list):
        return [item for entry in value for item in _advanced_scalar_values(entry)]
    if isinstance(value, dict):
        if "label" in value:
            return [value["label"], value["id"]] if value.get("id") else [value["label"]]
        if "value" in value:
            return [value["value"]]
        return [item for entry in value.values() for item in _advanced_scalar_values(entry)]
    return [] if value in (None, "") else [value]


def _build_advanced_index(
    metadata: dict[str, Any], field_definitions: list[Any]
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    fields: list[dict[str, Any]] = []
    relations: list[dict[str, str]] = []
    for definition in field_definitions:
        if not definition.is_public or not definition.is_searchable:
            continue
        raw = metadata.get(definition.name)
        if raw in (None, "", []):
            continue
        if definition.field_type == "relation":
            entries = raw if isinstance(raw, list) else [raw]
            for entry in entries:
                if not isinstance(entry, dict) or not entry.get("id"):
                    continue
                relations.append({
                    "source_field": definition.name,
                    "target_type": str((definition.settings or {}).get("target_type", "")),
                    "target_id": str(entry["id"]),
                    "relation_type": str(entry.get("relation_type", "")),
                })
            continue
        for value in _advanced_scalar_values(raw):
            item: dict[str, Any] = {"name": definition.name}
            if definition.field_type == "number":
                try:
                    item["number_value"] = float(value)
                except (TypeError, ValueError):
                    continue
            elif definition.field_type == "date" and isinstance(value, str):
                try:
                    lower, upper = date_bounds(value)
                except ValueError:
                    continue
                if lower is not None:
                    item["date_min"] = lower
                if upper is not None:
                    item["date_max"] = upper
            elif definition.field_type == "boolean" and isinstance(value, bool):
                item["bool_value"] = value
            elif definition.field_type in {
                "text", "richtext", "vocab", "vocab_free", "authority", "pid", "url",
            }:
                item["text_value"] = str(value)
                item["keyword_value"] = str(value)
            else:
                continue
            fields.append(item)
    return fields, relations


def inherited_facet_name(target_type: str, field_name: str) -> str:
    """Return the portal facet key for an inherited relation field."""
    return f"inherited_{target_type}_{field_name}"


def _build_doc(
    record_type: str,
    record: Any,
    rel_data: dict[str, list[str]] | None = None,
    searchable_fields: set[str] | None = None,
    facet_fields: set[str] | None = None,
    group_fields: set[str] | None = None,
    linked_data: dict[str, list[dict[str, Any]]] | None = None,
    inherited_facets: dict[str, list[str]] | None = None,
    metadata: dict[str, Any] | None = None,
    field_definitions: list[Any] | None = None,
) -> dict[str, Any]:
    # The Python attribute is metadata_ (DB column name is metadata)
    md: dict[str, Any] = _clean_metadata(
        metadata if metadata is not None else getattr(record, "metadata_", None) or {}
    )

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
    if record_type == "object":
        doc["collection_status"] = getattr(record, "collection_status", "active") or "active"

    # Build facet_* fields for fields marked as is_facet
    if facet_fields:
        field_types = {field.name: field.field_type for field in field_definitions or []}
        for field_name in facet_fields:
            val = md.get(field_name)
            if val is None:
                continue
            label = _extract_facet_value(val)
            if label:
                doc[f"facet_{field_name}"] = label
            if field_types.get(field_name) == "number":
                values: list[float] = []
                for value in _advanced_scalar_values(val):
                    try:
                        values.append(float(value))
                    except (TypeError, ValueError):
                        continue
                if values:
                    doc[f"number_facet_{field_name}"] = values if len(values) > 1 else values[0]

    # Index group field instances as nested ES objects under grp_* keys
    if group_fields:
        for field_name in group_fields:
            val = md.get(field_name)
            if isinstance(val, list) and val:
                doc[f"grp_{field_name}"] = val

    if rel_data:
        doc.update(rel_data)
    if linked_data:
        doc.update(linked_data)
    if inherited_facets:
        doc.update(inherited_facets)
    if field_definitions:
        advanced_fields, advanced_relations = _build_advanced_index(md, field_definitions)
        if advanced_fields:
            doc["adv_fields"] = advanced_fields
        if advanced_relations:
            doc["adv_relations"] = advanced_relations
    return doc


async def _load_linked_data(
    record_type: str,
    record_id: UUID,
    db: Any,
    inherited_config: dict[tuple[str, str | None], list[str]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[str]]]:
    """Load inherited fields from linked records for ES denormalization.

    inherited_config maps target_type -> list of field names to embed.
    Returns {"linked_occurrences": [{id, relation_type, inherited: {...}}, ...], ...}.
    """
    from sqlalchemy import and_, select

    from katalon.core.models import Entity, Object, Occurrence, Place, Procedure, Relation
    from katalon.services.public_metadata_service import filter_public_metadata, load_public_fields

    _MODEL_MAP: dict[str, Any] = {
        "object": Object, "entity": Entity, "place": Place, "occurrence": Occurrence, "procedure": Procedure,
    }
    result: dict[str, list[dict[str, Any]]] = {}
    facets: dict[str, list[str]] = {}

    stmt = select(Relation).where(
        and_(Relation.from_type == record_type, Relation.from_id == record_id)
    )
    relations = (await db.execute(stmt)).scalars().all()

    for rel in relations:
        fields = list({
            *inherited_config.get((rel.to_type, None), []),
            *inherited_config.get((rel.to_type, rel.relation_type), []),
        })
        if not fields:
            continue
        model = _MODEL_MAP.get(rel.to_type)
        if not model:
            continue
        linked_rec = await db.get(model, rel.to_id)
        if not linked_rec:
            continue
        public_fields = await load_public_fields(db, rel.to_type)
        subtype = getattr(linked_rec, f"{rel.to_type}_type", None)
        md = filter_public_metadata(linked_rec.metadata_ or {}, public_fields, subtype)
        inherited = {f: md[f] for f in fields if f in md}
        if not inherited:
            continue
        key = f"linked_{rel.to_type}s"
        result.setdefault(key, []).append({
            "id": str(rel.to_id),
            "relation_type": rel.relation_type,
            "inherited": inherited,
        })

        for field_name, value in inherited.items():
            facet_value = _extract_facet_value(value)
            if facet_value is None:
                continue
            facet_key = f"facet_{inherited_facet_name(rel.to_type, field_name)}"
            facets.setdefault(facet_key, []).extend(
                facet_value if isinstance(facet_value, list) else [facet_value]
            )

    return result, facets


async def _load_relation_titles(record_type: str, record_id: UUID, db: Any) -> dict[str, list[str]]:
    """Return names of related entities/places/occurrences for denormalisation in ES."""
    from sqlalchemy import and_, or_, select

    from katalon.core.models import Entity, Occurrence, Place, Relation
    from katalon.services.public_metadata_service import filter_public_metadata, load_public_fields

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
            public_fields = await load_public_fields(db, other_type)
            subtype = getattr(rec, f"{other_type}_type", None)
            title = _extract_title(filter_public_metadata(rec.metadata_ or {}, public_fields, subtype))
            if not title:
                title = getattr(rec, "idno", None) or ""
            if title:
                related[field_name].append(title)

    return related


async def build_index_doc(record_type: str, record: Any, db: Any = None) -> dict[str, Any]:
    """Build the ES document for a record without writing to ES."""
    from sqlalchemy import select

    from katalon.core.models import FieldDefinition
    from katalon.services.public_metadata_service import filter_public_metadata, load_public_fields

    rel_data: dict[str, list[str]] | None = None
    if db is not None:
        rel_data = await _load_relation_titles(record_type, record.id, db)

    searchable_fields: set[str] | None = None
    facet_fields: set[str] | None = None
    group_fields: set[str] | None = None
    inherited_config: dict[tuple[str, str | None], list[str]] = {}
    public_metadata: dict[str, Any] | None = None
    rows: list[Any] = []
    if db is not None:
        public_fields = await load_public_fields(db, record_type)
        public_metadata = filter_public_metadata(
            getattr(record, "metadata_", None),
            public_fields,
            getattr(record, f"{record_type}_type", None),
        )
        result = await db.execute(
            select(
                FieldDefinition.name,
                FieldDefinition.is_searchable,
                FieldDefinition.is_facet,
                FieldDefinition.is_public,
                FieldDefinition.field_type,
                FieldDefinition.settings,
            ).where(
                FieldDefinition.target_type == record_type,
                FieldDefinition.is_deleted.is_(False),
                FieldDefinition.parent_id.is_(None),
            )
        )
        rows = result.all()
        searchable_fields = {r.name for r in rows if r.is_searchable and r.is_public}
        facet_fields = {r.name for r in rows if r.is_facet and r.is_public}
        group_fields = {r.name for r in rows if r.field_type == "group" and r.is_public}
        for r in rows:
            if r.field_type == "relation" and r.is_public:
                s = r.settings or {}
                ifields = s.get("inherited_fields") or []
                target = s.get("target_type") or s.get("relation_target_type", "")
                if ifields and target:
                    key = (target, s.get("fixed_relation_type"))
                    existing = inherited_config.get(key, [])
                    inherited_config[key] = list(set(existing + ifields))

    linked_data: dict[str, list[dict[str, Any]]] = {}
    inherited_facets: dict[str, list[str]] = {}
    if inherited_config and db is not None:
        linked_data, inherited_facets = await _load_linked_data(
            record_type, record.id, db, inherited_config
        )

    return _build_doc(
        record_type, record, rel_data, searchable_fields, facet_fields, group_fields,
        linked_data, inherited_facets, public_metadata, rows,
    )


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
    extra_filters: dict[str, list[str]] | None = None,
    numeric_filters: dict[str, tuple[float | None, float | None]] | None = None,
    facet_fields: list[str] | None = None,
    rel_filters: dict[str, str] | None = None,
    record_types: tuple[str, ...] | None = None,
    subtitle_fields: dict[str, list[str]] | None = None,
    advanced_filter: dict[str, Any] | None = None,
    facet_sort: str = "count",
) -> dict[str, Any]:
    from_ = (page - 1) * page_size
    raw = await search_documents(
        query, record_type, status, from_, page_size,
        extra_filters=extra_filters,
        numeric_filters=numeric_filters,
        facet_fields=facet_fields,
        rel_filters=rel_filters,
        record_types=record_types,
        advanced_filter=advanced_filter,
        facet_sort=facet_sort,
    )

    hits = raw.get("hits", {})
    total = hits.get("total", {}).get("value", 0)
    items = []
    for h in hits.get("hits", []):
        source = h["_source"]
        item: dict[str, Any] = {"id": h["_id"], "score": h.get("_score"), **source}
        wanted = (subtitle_fields or {}).get(source.get("record_type", ""), [])
        values = {
            name: source[f"facet_{name}"]
            for name in wanted
            if name not in ("record_type", "status") and f"facet_{name}" in source
        }
        if values:
            item["subtitle_values"] = values
        items.append(item)

    aggs = raw.get("aggregations", {})
    facets: dict[str, list[dict[str, Any]]] = {}
    numeric_facets: dict[str, dict[str, float]] = {}
    for agg_key, agg_val in aggs.items():
        if agg_key.startswith("numeric_"):
            values = agg_val.get("filtered", {}).get("values", {})
            lower, upper = values.get("min"), values.get("max")
            if lower is not None and upper is not None:
                numeric_facets[agg_key[8:]] = {"min": lower, "max": upper}
            continue
        buckets = agg_val.get("filtered", {}).get("values", {}).get("buckets")
        if buckets is None:
            buckets = agg_val.get("buckets", [])
        facets[agg_key] = [
            {"value": b["key"], "count": b["doc_count"]}
            for b in buckets
        ]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
        "facets": facets,
        "numeric_facets": numeric_facets,
    }


def _contains(query: str, *columns: Any) -> Any:
    """Build a literal, case-insensitive PostgreSQL substring predicate."""
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped}%"
    return or_(*(column.ilike(pattern, escape="\\") for column in columns))


async def search_admin_data(db: AsyncSession, query: str, *, limit: int = 20) -> list[dict[str, str | None]]:
    """Search small, admin-only configuration tables without indexing them."""
    if not query.strip():
        return []
    q = query.strip()

    async def rows(stmt: Any) -> list[Any]:
        return list((await db.execute(stmt.limit(limit))).scalars().all())

    vocab_terms = (await db.execute(
        select(VocabularyTerm, Vocabulary.name)
        .join(Vocabulary)
        .where(_contains(q, VocabularyTerm.term, cast(VocabularyTerm.label, Text), Vocabulary.name))
        .limit(limit)
    )).all()
    items: list[dict[str, str | None]] = [
        {"id": str(term.id), "kind": "vocabulary_term", "title": term.term,
         "subtitle": vocab_name, "route": "vocab", "edit_id": vocab_name}
        for term, vocab_name in vocab_terms
    ]

    groups: list[tuple[Any, str, str, Any]] = [
        (select(User).where(_contains(q, User.email)), "user", "users", lambda row: (row.email, row.role, None)),
        (select(Vocabulary).where(_contains(q, Vocabulary.name)), "vocabulary", "vocab", lambda row: (row.name, None, row.name)),
        (select(StaticPage).where(_contains(q, StaticPage.slug, cast(StaticPage.title, Text), cast(StaticPage.content, Text))), "page", "pages", lambda row: (row.title.get("de") or row.title.get("en") or row.slug, row.slug, row.slug)),
        (select(OAISet).where(_contains(q, OAISet.set_spec, OAISet.set_name, OAISet.filter_q, cast(OAISet.filter_metadata, Text))), "oai_set", "oai-sets", lambda row: (row.set_name, row.set_spec, None)),
        (select(FieldDefinition).where(_contains(q, FieldDefinition.name, cast(FieldDefinition.label, Text))), "schema_field", "schema", lambda row: (row.label.get("de") or row.label.get("en") or row.name, row.target_type, row.target_type)),
        (select(RecordSubtype).where(_contains(q, RecordSubtype.name, RecordSubtype.description, cast(RecordSubtype.label, Text))), "subtype", "subtypes", lambda row: (row.label.get("de") or row.label.get("en") or row.name, row.primary_type, row.primary_type)),
        (select(FormVariant).where(FormVariant.is_deleted.is_(False), _contains(q, FormVariant.name, cast(FormVariant.label, Text))), "form_variant", "form-variants", lambda row: (row.label.get("de") or row.label.get("en") or row.name, row.target_type + (f".{row.target_subtype}" if row.target_subtype else ""), row.target_type + (f".{row.target_subtype}" if row.target_subtype else ""))),
        (select(Banner).where(_contains(q, Banner.message)), "banner", "banners", lambda row: (row.message, None, None)),
        (select(AuthoritySource).where(_contains(q, AuthoritySource.id, AuthoritySource.label)), "authority_source", "settings", lambda row: (row.label, row.id, "authorities")),
    ]
    for stmt, kind, route, display in groups:
        for row in await rows(stmt):
            title, subtitle, edit_id = display(row)
            items.append({
                "id": str(row.id), "kind": kind, "title": title, "subtitle": subtitle,
                "route": route, "edit_id": edit_id,
            })
    return items[:limit]
