# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import itertools
import logging
from collections.abc import AsyncIterator, Iterable, Sized
from typing import Any, cast

from elasticsearch import AsyncElasticsearch, NotFoundError

from katalon.config import settings

logger = logging.getLogger(__name__)

DEFAULT_REINDEX_BATCH_SIZE: int = getattr(settings, "es_reindex_batch_size", 500)

# Relation-derived facets (object/entity/place/occurrence/collection docs all carry
# these denormalized fields). Toggled per record type via portal_config.facet_fields,
# same mechanism as inherited_* facets — see api/v1/portal.py.
RELATED_FACET_NAMES = frozenset(
    {"related_entities", "related_places", "related_occurrences", "related_collections"}
)


class ReindexBatchError(RuntimeError):
    """Raised when one or more batches fail during reindex_type."""

    def __init__(
        self,
        message: str,
        *,
        target_type: str,
        failed_batches: list[dict[str, Any]],
        indexed_count: int,
    ) -> None:
        super().__init__(message)
        self.target_type = target_type
        self.failed_batches = failed_batches
        self.indexed_count = indexed_count


def get_es() -> AsyncElasticsearch:
    """Create a fresh ES client. Not cached – must be used within a single event loop."""
    return AsyncElasticsearch(settings.elasticsearch_url)


INDEX_SETTINGS: dict[str, Any] = {
    "settings": {
        "analysis": {
            "analyzer": {
                "katalon_default": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "asciifolding"],
                }
            }
        }
    },
    "mappings": {
        "dynamic_templates": [
            {
                "facet_fields": {
                    "match_pattern": "regex",
                    "match": "^facet_.*",
                    "mapping": {"type": "keyword"},
                }
            },
            {
                "numeric_facet_fields": {
                    "match_pattern": "regex",
                    "match": "^number_facet_.*",
                    "mapping": {"type": "double"},
                }
            },
            {
                # group field instances are indexed as nested objects under grp_{fieldname}
                "group_fields": {
                    "match_pattern": "regex",
                    "match": "^grp_.*",
                    "mapping": {"type": "nested"},
                }
            },
        ],
        "properties": {
            "record_type": {"type": "keyword"},
            "primary_media_id": {"type": "keyword"},
            "media_width": {"type": "integer"},
            "media_height": {"type": "integer"},
            "title": {
                "type": "text",
                "analyzer": "katalon_default",
                "fields": {"raw": {"type": "keyword"}},
            },
            "status": {"type": "keyword"},
            "metadata": {"type": "object", "enabled": False},
            "export_context": {"type": "object", "enabled": False},
            "search_text": {"type": "text", "analyzer": "katalon_default"},
            "created_at": {"type": "date"},
            "updated_at": {"type": "date"},
            "related_entities": {"type": "keyword"},
            "related_places": {"type": "keyword"},
            "related_occurrences": {"type": "keyword"},
            "related_collections": {"type": "keyword"},
            "adv_fields": {
                "type": "nested",
                "properties": {
                    "name": {"type": "keyword"},
                    "text_value": {"type": "text", "analyzer": "katalon_default"},
                    "keyword_value": {"type": "keyword"},
                    "number_value": {"type": "double"},
                    "date_min": {"type": "long"},
                    "date_max": {"type": "long"},
                    "bool_value": {"type": "boolean"},
                },
            },
            "adv_relations": {
                "type": "nested",
                "properties": {
                    "source_field": {"type": "keyword"},
                    "target_type": {"type": "keyword"},
                    "target_id": {"type": "keyword"},
                    "relation_type": {"type": "keyword"},
                },
            },
        },
    },
}

INDEX_NAME = settings.es_index_name
ALIAS_NAME = "katalon"  # stable alias used by all queries


async def ensure_index() -> None:
    es = get_es()
    exists = await es.indices.exists(index=INDEX_NAME)
    if not exists:
        await es.indices.create(index=INDEX_NAME, body=INDEX_SETTINGS)
    else:
        # Idempotently apply mapping changes (e.g. new fields)
        await es.indices.put_mapping(index=INDEX_NAME, body=INDEX_SETTINGS["mappings"])
    # Ensure the alias points to the main index
    alias_exists = await es.indices.exists_alias(name=ALIAS_NAME)
    if not alias_exists:
        await es.indices.put_alias(index=INDEX_NAME, name=ALIAS_NAME)


async def reindex_type(
    target_type: str,
    records: Iterable[tuple[str, dict[str, Any]]],
    *,
    batch_size: int = DEFAULT_REINDEX_BATCH_SIZE,
    raise_on_error: bool = True,
) -> int:
    """Delete all docs of target_type and re-index the supplied records in batches.

    Returns the number of documents successfully indexed.
    """
    if batch_size <= 0:
        raise ValueError(f"batch_size must be positive, got {batch_size}")

    es = get_es()
    try:
        # Delete existing docs for this type
        await es.delete_by_query(
            index=INDEX_NAME,
            body={"query": {"term": {"record_type": target_type}}},
            refresh=True,
        )

        total_records = len(records) if isinstance(records, Sized) else None
        if total_records == 0:
            return 0
        total_batches = (
            (total_records + batch_size - 1) // batch_size if total_records is not None else None
        )

        total_indexed = 0
        failed_batches: list[dict[str, Any]] = []

        for batch_idx, batch in enumerate(itertools.batched(records, batch_size), start=1):
            batch_label = (
                f"{batch_idx}/{total_batches}" if total_batches is not None else str(batch_idx)
            )
            ops: list[dict[str, Any]] = []
            doc_ids: list[str] = []
            for doc_id, body in batch:
                ops.append({"index": {"_index": INDEX_NAME, "_id": doc_id}})
                ops.append(body)
                doc_ids.append(doc_id)

            try:
                resp = await es.bulk(body=ops, refresh=False)
                items = resp.get("items", [])
                item_errors = [item for item in items if "error" in item.get("index", {})]
                if item_errors:
                    for item in item_errors:
                        idx_info = item.get("index", {})
                        err_doc_id = idx_info.get("_id", "unknown")
                        err_detail = idx_info.get("error", {})
                        logger.error(
                            "reindex_type(%s) item error in batch %s for record %s: %s",
                            target_type,
                            batch_label,
                            err_doc_id,
                            err_detail,
                        )
                    failed_batches.append(
                        {
                            "batch": batch_idx,
                            "batch_label": batch_label,
                            "error_type": "item_errors",
                            "doc_ids": [
                                item.get("index", {}).get("_id", "") for item in item_errors
                            ],
                            "error": f"{len(item_errors)} item error(s) in batch",
                        }
                    )
                indexed_in_batch = len(batch) - len(item_errors)
                total_indexed += indexed_in_batch
            except Exception as exc:
                logger.exception(
                    "reindex_type(%s) bulk request failed on batch %s (%d records): %s. Record IDs: %s",
                    target_type,
                    batch_label,
                    len(batch),
                    exc,
                    doc_ids[:10],
                )
                failed_batches.append(
                    {
                        "batch": batch_idx,
                        "batch_label": batch_label,
                        "error_type": "bulk_exception",
                        "doc_ids": doc_ids,
                        "error": str(exc),
                    }
                )

        # Always refresh the index so successfully indexed documents are searchable and not lost
        if total_indexed > 0:
            try:
                await es.indices.refresh(index=INDEX_NAME)
            except Exception:
                logger.warning(
                    "Failed to refresh index %s after reindex_type(%s)",
                    INDEX_NAME,
                    target_type,
                    exc_info=True,
                )

        if failed_batches and raise_on_error:
            failed_count = sum(len(fb["doc_ids"]) for fb in failed_batches)
            details = "; ".join(
                f"Batch {fb['batch_label']} ({len(fb['doc_ids'])} records, e.g. {fb['doc_ids'][:3]}): {fb['error']}"
                for fb in failed_batches
            )
            msg = (
                f"Reindex for '{target_type}' completed with failures: "
                f"{len(failed_batches)} batch(es) failed ({failed_count} records not indexed). "
                f"{total_indexed} records successfully indexed. Details: {details}"
            )
            raise ReindexBatchError(
                msg,
                target_type=target_type,
                failed_batches=failed_batches,
                indexed_count=total_indexed,
            )

        return total_indexed
    finally:
        await es.close()


async def index_document(doc_id: str, body: dict[str, Any]) -> None:
    es = get_es()
    await es.index(index=INDEX_NAME, id=doc_id, body=body, refresh=True)


async def count_by_type(record_type: str) -> int:
    es = get_es()
    query = {"query": {"term": {"record_type": record_type}}}
    try:
        resp = await es.count(index=INDEX_NAME, body=query)
    except NotFoundError:
        return 0
    return int(resp["count"])


async def list_ids_by_type(record_type: str, *, batch_size: int = 1000) -> set[str]:
    """Return all document IDs for a record type via scroll/PIT-free pagination."""
    es = get_es()
    ids: set[str] = set()
    query = {"query": {"term": {"record_type": record_type}}, "_source": False, "size": batch_size}
    try:
        resp = await es.search(index=INDEX_NAME, body=query, scroll="2m")
    except NotFoundError:
        return ids
    scroll_id = resp.get("_scroll_id")
    hits = resp["hits"]["hits"]
    try:
        while hits:
            ids.update(hit["_id"] for hit in hits)
            resp = await es.scroll(scroll_id=scroll_id, scroll="2m")
            scroll_id = resp.get("_scroll_id")
            hits = resp["hits"]["hits"]
    finally:
        if scroll_id:
            await es.clear_scroll(scroll_id=scroll_id)
    return ids


async def iter_hits_by_type(
    record_type: str, *, batch_size: int = 500
) -> AsyncIterator[dict[str, Any]]:
    """Yield full ES hits (id + _source) for a record type via scroll, regardless of status."""
    es = get_es()
    query = {"query": {"term": {"record_type": record_type}}, "size": batch_size}
    try:
        resp = await es.search(index=INDEX_NAME, body=query, scroll="2m")
    except NotFoundError:
        return
    scroll_id = resp.get("_scroll_id")
    hits = resp["hits"]["hits"]
    try:
        while hits:
            for hit in hits:
                yield hit
            resp = await es.scroll(scroll_id=scroll_id, scroll="2m")
            scroll_id = resp.get("_scroll_id")
            hits = resp["hits"]["hits"]
    finally:
        if scroll_id:
            await es.clear_scroll(scroll_id=scroll_id)


async def delete_document(doc_id: str) -> None:
    es = get_es()
    try:
        await es.delete(index=INDEX_NAME, id=doc_id)
    except NotFoundError:
        pass


async def search_documents(
    query: str | None,
    record_type: str | None,
    status: str | None,
    from_: int,
    size: int,
    extra_filters: dict[str, list[str]] | None = None,
    numeric_filters: dict[str, tuple[float | None, float | None]] | None = None,
    facet_fields: list[str] | None = None,
    rel_filters: dict[str, list[str] | str] | None = None,
    status_facet: list[str] | None = None,
    record_types: tuple[str, ...] | None = None,
    advanced_filter: dict[str, Any] | None = None,
    facet_sort: str = "count",
    sort: str | None = None,
) -> dict[str, Any]:
    es = get_es()

    must: list[dict[str, Any]] = []
    # Filters that narrow every facet's own aggregation too, including itself
    # (record_type/advanced query define the record set being browsed, not a
    # togglable multi-select facet).
    base_filters: list[dict[str, Any]] = []

    if query:
        q = query.strip()
        # Add trailing wildcard for prefix/autocomplete unless query already has operators
        if q and not any(c in q for c in (":", '"', "*", "?", "+", "-", "~", "(")):
            q = q + "*"
        must.append(
            {
                "query_string": {
                    "query": q,
                    "fields": ["title^3", "search_text^2"],
                    "default_operator": "AND",
                    "lenient": True,
                    "allow_leading_wildcard": True,
                }
            }
        )
    else:
        must.append({"match_all": {}})

    if record_type:
        base_filters.append({"term": {"record_type": record_type}})
    elif record_types:
        base_filters.append({"terms": {"record_type": list(record_types)}})
    if status:
        # Security-enforced status (e.g. anonymous callers locked to "public") is
        # never excluded from its own aggregation — unlike status_facet below, it
        # must not leak counts for statuses the caller is not allowed to see.
        base_filters.append({"term": {"status": status}})
    if advanced_filter:
        base_filters.append(advanced_filter)

    def _term_filter(field: str, values: list[str]) -> dict[str, Any]:
        return {"term": {field: values[0]}} if len(values) == 1 else {"terms": {field: values}}

    def _facet_doc_field(field: str) -> str:
        # Direct fields aggregate against facet_all_* (present for every public
        # field, so is_facet toggles need no reindex). inherited_* facets keep
        # their legacy top-level facet_* document fields.
        return f"facet_{field}" if field.startswith("inherited_") else f"facet_all_{field}"

    # Exclusion-aware facet filters: each is additive (multi-select, OR within the
    # facet) and excluded from its own aggregation, so picking one value never hides
    # the sibling values a user could still add.
    facet_filters: dict[str, dict[str, Any]] = {
        field: _term_filter(_facet_doc_field(field), values)
        for field, values in (extra_filters or {}).items()
        if values
    }
    if status_facet:
        facet_filters["status"] = _term_filter("status", status_facet)
    for field, values in (rel_filters or {}).items():
        vals = [values] if isinstance(values, str) else list(values)
        if vals:
            facet_filters[field] = _term_filter(field, vals)
    numeric_facet_filters = {
        field: {
            "range": {
                f"number_facet_all_{field}": {
                    key: value
                    for key, value in {"gte": lower, "lte": upper}.items()
                    if value is not None
                }
            }
        }
        for field, (lower, upper) in (numeric_filters or {}).items()
        if lower is not None or upper is not None
    }

    filters = [*base_filters, *facet_filters.values(), *numeric_facet_filters.values()]

    es_query: dict[str, Any] = {"bool": {"must": must, "filter": filters}}

    facet_order = {"_key": "asc"} if facet_sort == "alpha" else {"_count": "desc"}

    def _self_excluding_agg(
        terms_field: str, exclude_key: str, agg_size: int, order: dict[str, str]
    ) -> dict[str, Any]:
        aggregation_filters = [
            value for name, value in facet_filters.items() if name != exclude_key
        ]
        return {
            "global": {},
            "aggs": {
                "filtered": {
                    "filter": {
                        "bool": {
                            "must": must,
                            "filter": [
                                *base_filters,
                                *aggregation_filters,
                                *numeric_facet_filters.values(),
                            ],
                        }
                    },
                    "aggs": {
                        "values": {
                            "terms": {"field": terms_field, "size": agg_size, "order": order}
                        }
                    },
                }
            },
        }

    aggs: dict[str, Any] = {
        "by_type": {"terms": {"field": "record_type", "size": 10}},
        "by_status": _self_excluding_agg("status", "status", 10, {"_count": "desc"}),
    }
    # Fetch generously beyond the portal's initially visible count so "show
    # more" can reveal further values without a second round-trip.
    for field in facet_fields or []:
        if field in RELATED_FACET_NAMES:
            aggs[field] = _self_excluding_agg(field, field, 30, {"_count": "desc"})
            continue
        aggs[f"meta_{field}"] = _self_excluding_agg(_facet_doc_field(field), field, 100, facet_order)
        numeric_aggregation_filters = [
            value for name, value in numeric_facet_filters.items() if name != field
        ]
        aggs[f"numeric_{field}"] = {
            "global": {},
            "aggs": {
                "filtered": {
                    "filter": {
                        "bool": {
                            "must": must,
                            "filter": [
                                *base_filters,
                                *facet_filters.values(),
                                *numeric_aggregation_filters,
                            ],
                        }
                    },
                    "aggs": {"values": {"stats": {"field": f"number_facet_all_{field}"}}},
                }
            },
        }

    SORT_CLAUSES: dict[str, list[dict[str, Any]]] = {
        "idno_asc": [{"idno.keyword": "asc"}],
        "title_asc": [{"title.raw": "asc"}],
        "newest": [{"created_at": "desc"}],
        "oldest": [{"created_at": "asc"}],
    }
    body: dict[str, Any] = {
        "query": es_query,
        "aggs": aggs,
        "from": from_,
        "size": size,
        "track_total_hits": True,
    }
    if sort in SORT_CLAUSES:
        body["sort"] = SORT_CLAUSES[sort]
    elif not query:
        # match_all gives every document an identical constant score, so
        # "relevance" sort on an empty query would otherwise fall back to
        # arbitrary Lucene segment order. Use a deterministic order instead.
        body["sort"] = SORT_CLAUSES["idno_asc"]
    result = await es.search(index=INDEX_NAME, body=body)
    return cast(dict[str, Any], result.body)


async def search_ids_by_filter(
    record_type: str,
    advanced_filter: dict[str, Any],
    *,
    limit: int = 10000,
) -> tuple[list[str], bool]:
    """Return public matching IDs and whether the result exceeded the bounded intermediate set."""
    es = get_es()
    filters: list[dict[str, Any]] = [
        {"term": {"record_type": record_type}},
        {"term": {"status": "public"}},
        advanced_filter,
    ]
    result = await es.search(
        index=ALIAS_NAME,
        body={
            "query": {"bool": {"filter": filters}},
            "_source": False,
            "size": limit,
            "track_total_hits": True,
        },
    )
    body = cast(dict[str, Any], result.body)
    hits = body.get("hits", {})
    total = int(hits.get("total", {}).get("value", 0))
    return [str(hit["_id"]) for hit in hits.get("hits", [])], total > limit
