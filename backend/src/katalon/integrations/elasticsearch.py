# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import asyncio
import itertools
import json
import logging
import re
import uuid
import weakref
from collections.abc import AsyncIterator, Iterable, Iterator
from datetime import UTC, datetime
from typing import Any, cast

from elasticsearch import AsyncElasticsearch, BadRequestError, NotFoundError

from katalon.config import settings
from katalon.core.visibility import PUBLIC_STATUSES

logger = logging.getLogger(__name__)

# Relation-derived facets (object/entity/place/occurrence/collection docs all carry
# these denormalized fields). Toggled per record type via portal_config.facet_fields,
# same mechanism as inherited_* facets — see api/v1/portal.py.
RELATED_FACET_NAMES = frozenset(
    {"related_entities", "related_places", "related_occurrences", "related_collections"}
)


# ES's default per-shard result-window safety cap (index.max_result_window).
# Deep pages past this depth are served via a reversed-sort tail fetch instead
# of raising `from` — see search_documents().
FORWARD_LIMIT = 10_000


def _reverse_sort(clauses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flip asc/desc on every clause of a deterministic sort spec."""
    flipped: list[dict[str, Any]] = []
    for clause in clauses:
        for field, direction in clause.items():
            flipped.append({field: "desc" if direction == "asc" else "asc"})
    return flipped


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


# One client per event loop: aiohttp sessions are bound to the loop that
# created them. The API process runs one loop (one pooled client for its
# lifetime); each Celery task runs its own asyncio.run loop and closes its
# client via close_es() before the loop ends. Previously every call created a
# client and most callers never closed it — one leaked HTTP session per
# indexed record in the worker.
_clients: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, AsyncElasticsearch] = (
    weakref.WeakKeyDictionary()
)


def get_es() -> AsyncElasticsearch:
    """Return the ES client of the running event loop (created on first use).
    Callers must not close it; the loop owner calls ``close_es()``."""
    loop = asyncio.get_running_loop()
    client = _clients.get(loop)
    if client is None:
        client = AsyncElasticsearch(settings.elasticsearch_url)
        _clients[loop] = client
    return client


async def close_es() -> None:
    """Close the running loop's client (API shutdown, end of a worker task)."""
    client = _clients.pop(asyncio.get_running_loop(), None)
    if client is not None:
        await client.close()


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
        # Dynamically mapped values (group instances under grp_*) must never be
        # guessed as dates: an EDTF value like "1884/1919" or "1890/" next to a
        # detected "1918-03-21" made Elasticsearch reject the whole document.
        "date_detection": False,
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
            "subtype": {"type": "keyword"},
            "object_type": {"type": "keyword"},
            "primary_media_id": {"type": "keyword"},
            # Returned only, never queried.
            "primary_media_iiif": {"type": "keyword", "index": False, "doc_values": False},
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
            # export_context.schema_version, queryable (stale copies after an update)
            "export_context_version": {"type": "integer"},
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
                    # Free relations (relations table): seen from this record.
                    "direction": {"type": "keyword"},
                },
            },
        },
    },
}

# The name every read and write uses. On current installations it is an alias
# onto a dated physical index (`<name>_<YYYYmmddHHMMSS>_<random>`), so a full rebuild can
# fill a fresh index and switch atomically. Older installations still have a
# concrete index under this name; the first full rebuild replaces it with the
# alias in the same atomic request.
INDEX_NAME = settings.es_index_name
# While a full rebuild fills a new physical index, single-document writes go to
# both indices so the new one does not miss them (see workers/index_tasks.py).
SHADOW_INDEX_KEY = f"katalon:reindex:shadow:{INDEX_NAME}"


def new_physical_index_name() -> str:
    # Timestamp for operators, random suffix so two indices created within the
    # same second (fresh install + immediate rebuild) never collide.
    return f"{INDEX_NAME}_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"


async def ensure_index() -> None:
    es = get_es()
    if await es.indices.exists(index=INDEX_NAME):
        # Alias or legacy concrete index: idempotently apply mapping additions.
        await es.indices.put_mapping(index=INDEX_NAME, body=INDEX_SETTINGS["mappings"])
        return
    await create_physical_index(new_physical_index_name(), alias=True)


async def create_physical_index(name: str, *, alias: bool = False) -> None:
    body: dict[str, Any] = dict(INDEX_SETTINGS)
    if alias:
        body["aliases"] = {INDEX_NAME: {}}
    await get_es().indices.create(index=name, body=body)


async def swap_alias(new_index: str) -> list[str]:
    """Point INDEX_NAME at ``new_index`` atomically and delete the indices it
    pointed at before. Returns the previous index names (cleanup failures are logged)."""
    es = get_es()
    if await es.indices.exists_alias(name=INDEX_NAME):
        old = [name for name in (await es.indices.get_alias(name=INDEX_NAME)).body if name != new_index]
        actions: list[dict[str, Any]] = [
            {"remove": {"index": name, "alias": INDEX_NAME}} for name in old
        ]
        actions.append({"add": {"index": new_index, "alias": INDEX_NAME}})
        await es.indices.update_aliases(body={"actions": actions})
        for name in old:
            try:
                await es.indices.delete(index=name)
            except Exception:
                logger.warning("old index %s could not be removed after alias switch", name, exc_info=True)
        return old
    if not await es.indices.exists(index=INDEX_NAME):
        await es.indices.put_alias(index=new_index, name=INDEX_NAME)
        return []
    # Legacy concrete index under the alias name: remove it in the same atomic
    # request that creates the alias, so the name never resolves to nothing.
    await es.indices.update_aliases(
        body={
            "actions": [
                {"remove_index": {"index": INDEX_NAME}},
                {"add": {"index": new_index, "alias": INDEX_NAME}},
            ]
        }
    )
    return [INDEX_NAME]


async def delete_physical_index(name: str) -> None:
    try:
        await get_es().indices.delete(index=name)
    except NotFoundError:
        pass


async def _shadow_index() -> str | None:
    """Target of an in-progress full rebuild, if any. Redis errors are logged
    and ignored: the rebuild's catch-up pass re-reads changed records anyway."""
    try:
        import redis.asyncio as redis_async

        client = redis_async.from_url(settings.redis_url, decode_responses=True)  # type: ignore[no-untyped-call]
        try:
            value = await client.get(SHADOW_INDEX_KEY)
        finally:
            await client.aclose()
        return str(value) if value else None
    except Exception as exc:
        logger.warning("could not read reindex shadow index: %s", exc)
        return None


def _ndjson_line(data: dict[str, Any]) -> bytes:
    return json.dumps(data, ensure_ascii=False, default=str).encode("utf-8") + b"\n"


def _bulk_chunks(
    target_type: str, docs: list[tuple[str, dict[str, Any]]], max_bytes: int, index: str
) -> Iterator[tuple[list[bytes], list[str]]]:
    """Serialize docs once and group them into request bodies of at most
    ``max_bytes`` (a single larger document forms its own request)."""
    lines: list[bytes] = []
    ids: list[str] = []
    size = 0
    for doc_id, body in docs:
        action = _ndjson_line({"index": {"_index": index, "_id": doc_id}})
        source = _ndjson_line({"record_type": target_type, **body})
        item_size = len(action) + len(source)
        if lines and size + item_size > max_bytes:
            yield lines, ids
            lines, ids, size = [], [], 0
        lines += [action, source]
        ids.append(doc_id)
        size += item_size
    if lines:
        yield lines, ids


async def bulk_index_documents(
    es: AsyncElasticsearch,
    target_type: str,
    docs: list[tuple[str, dict[str, Any]]],
    *,
    max_bytes: int | None = None,
    index: str = INDEX_NAME,
) -> tuple[int, list[str]]:
    """Index docs (overwriting by id) in byte-bounded _bulk requests.
    Returns (indexed count, failed ids).

    Used by the streaming bulk reindex, which overwrites documents in place
    instead of deleting the whole type first — the portal keeps serving the
    previous state of a record until its new document lands.
    """
    limit = max_bytes or settings.es_bulk_max_bytes
    indexed = 0
    failed: list[str] = []
    for lines, ids in _bulk_chunks(target_type, docs, limit, index):
        try:
            # Pre-serialized NDJSON lines are forwarded unchanged by the client.
            resp = await es.bulk(operations=cast(Any, lines), refresh=False)
        except Exception as exc:
            logger.exception(
                "bulk index for '%s' failed (%d docs, %d bytes): %s",
                target_type,
                len(ids),
                sum(len(line) for line in lines),
                exc,
            )
            failed.extend(ids)
            continue
        chunk_failed = 0
        for item in resp.get("items", []):
            info = item.get("index", {})
            if "error" in info:
                chunk_failed += 1
                failed.append(str(info.get("_id", "")))
                logger.error(
                    "bulk index item error for %s/%s: %s",
                    target_type,
                    info.get("_id"),
                    info["error"],
                )
        indexed += len(ids) - chunk_failed
    return indexed, failed


async def delete_documents(
    es: AsyncElasticsearch, doc_ids: Iterable[str], *, index: str = INDEX_NAME
) -> int:
    """Delete documents by id (missing ids are ignored). Returns deleted count."""
    ids = list(doc_ids)
    deleted = 0
    for batch in itertools.batched(ids, 1000, strict=False):
        resp = await es.delete_by_query(
            index=index, body={"query": {"ids": {"values": list(batch)}}}, refresh=False
        )
        deleted += int(resp.get("deleted", 0))
    return deleted


async def index_document(doc_id: str, body: dict[str, Any]) -> None:
    es = get_es()
    await es.index(index=INDEX_NAME, id=doc_id, body=body, refresh=True)
    if shadow := await _shadow_index():
        try:
            await es.index(index=shadow, id=doc_id, body=body, refresh=False)
        except Exception:
            logger.warning("shadow write to %s failed for %s", shadow, doc_id, exc_info=True)


async def count_by_type(record_type: str) -> int:
    es = get_es()
    query = {"query": {"term": {"record_type": record_type}}}
    try:
        resp = await es.count(index=INDEX_NAME, body=query)
    except NotFoundError:
        return 0
    return int(resp["count"])


async def count_stale_export_contexts(current_version: int, record_types: Iterable[str]) -> int:
    """Documents of exportable types whose export_context was written by an older
    Katalon (or is missing)."""
    es = get_es()
    query = {
        "query": {
            "bool": {
                "filter": [{"terms": {"record_type": sorted(record_types)}}],
                "must_not": [{"range": {"export_context_version": {"gte": current_version}}}],
            }
        }
    }
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
    record_type: str, *, batch_size: int = 500, public_only: bool = False
) -> AsyncIterator[dict[str, Any]]:
    """Yield full ES hits (id + _source) for a record type via scroll.

    `public_only=True` restricts to `status in PUBLIC_STATUSES` (#389) — used
    by bulk export for callers without record-read permission on the type,
    mirroring `apply_public_visibility()`'s DB-query equivalent.
    """
    es = get_es()
    filters: list[dict[str, Any]] = [{"term": {"record_type": record_type}}]
    if public_only:
        filters.append({"terms": {"status": list(PUBLIC_STATUSES)}})
    query = {"query": {"bool": {"filter": filters}}, "size": batch_size}
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
    for index in (INDEX_NAME, await _shadow_index()):
        if index is None:
            continue
        try:
            await es.delete(index=index, id=doc_id)
        except NotFoundError:
            pass


async def search_documents(
    query: str | None,
    record_type: str | None,
    status: str | tuple[str, ...] | None,
    from_: int,
    size: int,
    extra_filters: dict[str, list[str]] | None = None,
    numeric_filters: dict[str, tuple[float | None, float | None]] | None = None,
    facet_fields: list[str] | None = None,
    rel_filters: dict[str, list[str] | str] | None = None,
    status_facet: list[str] | None = None,
    subtype_facet: list[str] | None = None,
    record_types: tuple[str, ...] | None = None,
    advanced_filter: dict[str, Any] | None = None,
    facet_sort: str = "count",
    facet_sorts: dict[str, str] | None = None,
    sort: str | None = None,
    full_visibility_types: tuple[str, ...] | None = None,
    facet_specs: dict[str, tuple[str, str, str]] | None = None,
    tree_aggs: dict[str, tuple[str, str, list[str]]] | None = None,
) -> dict[str, Any]:
    """``facet_specs`` maps a facet name to (filter field, aggregation field,
    kind) for facets whose index fields differ from facet_all_<name> (date
    buckets, vocabulary paths, relation facets; see services/facet_service).
    ``tree_aggs`` maps an aggregation key to (facet name, field, term ids):
    counts for exactly those ids, e.g. the children of one expanded node."""
    es = get_es()
    specs = facet_specs or {}

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
        base_filters.append(
            {"terms": {"status": list(status)}}
            if isinstance(status, tuple)
            else {"term": {"status": status}}
        )
    if full_visibility_types is not None:
        # Every hit must be either publicly visible, or of a record_type the
        # caller has an explicit read permission for (see
        # core.visibility.readable_record_types). This is independent from
        # the `status` filter above, which narrows further on top of it.
        should: list[dict[str, Any]] = [{"terms": {"status": list(PUBLIC_STATUSES)}}]
        if full_visibility_types:
            should.append({"terms": {"record_type": list(full_visibility_types)}})
        base_filters.append({"bool": {"should": should, "minimum_should_match": 1}})
    if advanced_filter:
        base_filters.append(advanced_filter)

    def _term_filter(field: str, values: list[str]) -> dict[str, Any]:
        return {"term": {field: values[0]}} if len(values) == 1 else {"terms": {field: values}}

    def _facet_doc_field(field: str) -> str:
        # Direct fields aggregate against facet_all_* (present for every public
        # field, so is_facet toggles need no reindex). inherited_* facets keep
        # their legacy top-level facet_* document fields.
        if field in specs:
            return specs[field][0]
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
    if subtype_facet:
        facet_filters["subtype"] = _term_filter("subtype", subtype_facet)
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
        "by_subtype": _self_excluding_agg("subtype", "subtype", 30, {"_count": "desc"}),
    }
    # Fetch generously beyond the portal's initially visible count so "show
    # more" can reveal further values without a second round-trip.
    for field in facet_fields or []:
        field_sort = (facet_sorts or {}).get(field, facet_sort)
        field_order = {"_key": "asc"} if field_sort == "alpha" else {"_count": "desc"}
        if field in RELATED_FACET_NAMES:
            aggs[field] = _self_excluding_agg(
                field, field, 100 if field_sort == "alpha" else 30, field_order
            )
            continue
        kind = specs[field][2] if field in specs else "terms"
        if kind == "tree":
            continue  # counted per node via tree_aggs
        if kind == "date":
            # Chronological, and enough buckets for every year of a few centuries.
            aggs[f"meta_{field}"] = _self_excluding_agg(specs[field][1], field, 500, {"_key": "asc"})
            continue
        if kind == "boolean":
            aggs[f"meta_{field}"] = _self_excluding_agg(
                _facet_doc_field(field), field, 10, {"_count": "desc"}
            )
            continue
        if kind == "relation":
            # Buckets are "<uuid>|<title>", so _key order would sort by UUID;
            # search_service sorts by title when field_sort == "alpha".
            agg = _self_excluding_agg(
                specs[field][1], field, 500 if field_sort == "alpha" else 100, {"_count": "desc"}
            )
            selected = [str(v) for v in (extra_filters or {}).get(field) or []]
            if selected:
                # A selected target outside the top buckets would come back without its
                # title (the active filter would show the bare id).
                pattern = "(" + "|".join(re.escape(v) for v in selected) + ")\\|.*"
                agg["aggs"]["filtered"]["aggs"]["selected"] = {
                    "terms": {"field": specs[field][1], "size": len(selected), "include": pattern}
                }
            aggs[f"meta_{field}"] = agg
            continue
        aggs[f"meta_{field}"] = _self_excluding_agg(_facet_doc_field(field), field, 100, field_order)
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

    for agg_key, (facet_name, terms_field, ids) in (tree_aggs or {}).items():
        if not ids:
            continue
        agg = _self_excluding_agg(terms_field, facet_name, len(ids), {"_count": "desc"})
        agg["aggs"]["filtered"]["aggs"]["values"]["terms"]["include"] = ids
        aggs[agg_key] = agg

    SORT_CLAUSES: dict[str, list[dict[str, Any]]] = {
        "idno_asc": [{"idno.keyword": "asc"}],
        "title_asc": [{"title.raw": "asc"}],
        "newest": [{"created_at": "desc"}],
        "oldest": [{"created_at": "asc"}],
    }
    sort_clauses = SORT_CLAUSES.get(sort or "")
    if sort_clauses is None and not query:
        # match_all gives every document an identical constant score, so
        # "relevance" sort on an empty query would otherwise fall back to
        # arbitrary Lucene segment order. Use a deterministic order instead.
        sort_clauses = SORT_CLAUSES["idno_asc"]

    body: dict[str, Any] = {"query": es_query, "aggs": aggs, "track_total_hits": True}
    if sort_clauses:
        body["sort"] = sort_clauses

    async def _run(query_body: dict[str, Any]) -> dict[str, Any]:
        try:
            result = await es.search(index=INDEX_NAME, body=query_body)
        except BadRequestError as exc:
            from fastapi import HTTPException

            logger.info("search rejected by Elasticsearch: %s", exc)

            raise HTTPException(
                status_code=422, detail="Die Suchanfrage enthält ungültige Suchsyntax."
            ) from exc
        return cast(dict[str, Any], result.body)

    if from_ + size <= FORWARD_LIMIT:
        return await _run({**body, "from": from_, "size": size})

    if not sort_clauses:
        # Relevance ranking has no cheap tail: reversing "sort by score" isn't a
        # reliable inverse of the forward order across shards. Deep pages past
        # FORWARD_LIMIT need a deterministic sort (idno/title/date) instead.
        raise ValueError(
            "Diese Seite liegt zu tief in den Volltext-Trefferergebnissen. "
            "Relevanzsortierung unterstützt keine so tiefe Paginierung – Suche "
            "eingrenzen oder eine feste Sortierung (Titel/ID/Datum) wählen."
        )

    # Deterministic sort: fetch the tail via a reversed sort instead of a deep
    # `from`, so "jump to the last page" costs O(page_size) regardless of how
    # large the collection is — no result-window ceiling for front or back.
    pilot = await _run({"query": es_query, "size": 0, "track_total_hits": True})
    total = int(pilot.get("hits", {}).get("total", {}).get("value", 0))
    effective_size = min(size, max(0, total - from_))
    if effective_size <= 0:
        pilot["hits"]["hits"] = []
        return pilot
    reverse_from = max(0, total - from_ - effective_size)
    if reverse_from + effective_size > FORWARD_LIMIT:
        # Neither end is cheap: the requested page sits near the middle of a
        # very large result set that no one-click UI affordance can reach.
        raise ValueError(
            "Diese Seite liegt zu tief in einer sehr großen Ergebnismenge "
            "(weder vom Anfang noch vom Ende her günstig erreichbar). Suche "
            "weiter eingrenzen."
        )
    reversed_body = {
        **body,
        "sort": _reverse_sort(sort_clauses),
        "from": reverse_from,
        "size": effective_size,
    }
    result = await _run(reversed_body)
    result["hits"]["hits"] = list(reversed(result["hits"]["hits"]))
    return result


ADVANCED_RECORD_TYPES = ("object", "entity", "place", "occurrence")


async def advanced_relation_types(record_type: str) -> list[dict[str, Any]]:
    """Free relation types usable for one record type: type, direction, other side, count.

    Only outgoing relations are indexed. Outgoing types come from the record type's
    own documents; incoming ones from other documents' outgoing relations to it.
    """
    es = get_es()
    free_outgoing = {"exists": {"field": "adv_relations.direction"}}
    result = await es.search(
        index=INDEX_NAME,
        body={
            "size": 0,
            "query": {"bool": {"filter": [
                {"terms": {"record_type": list(ADVANCED_RECORD_TYPES)}},
                {"terms": {"status": list(PUBLIC_STATUSES)}},
            ]}},
            "aggs": {
                "outgoing": {
                    "filter": {"term": {"record_type": record_type}},
                    "aggs": {"rels": {"nested": {"path": "adv_relations"}, "aggs": {"free": {
                        "filter": free_outgoing,
                        "aggs": {"types": {
                            "multi_terms": {
                                "terms": [
                                    {"field": "adv_relations.relation_type"},
                                    {"field": "adv_relations.target_type"},
                                ],
                                "size": 500,
                            },
                            "aggs": {"records": {"reverse_nested": {}}},
                        }},
                    }}}},
                },
                "incoming": {
                    "terms": {"field": "record_type", "size": len(ADVANCED_RECORD_TYPES)},
                    "aggs": {"rels": {"nested": {"path": "adv_relations"}, "aggs": {"to_me": {
                        "filter": {"bool": {"filter": [
                            free_outgoing,
                            {"term": {"adv_relations.target_type": record_type}},
                        ]}},
                        "aggs": {"types": {
                            "terms": {"field": "adv_relations.relation_type", "size": 500},
                            "aggs": {"records": {"reverse_nested": {}}},
                        }},
                    }}}},
                },
            },
        },
    )
    aggs = cast(dict[str, Any], result.body).get("aggregations", {})
    options = [
        {
            "relation_type": bucket["key"][0],
            "direction": "outgoing",
            "target_type": bucket["key"][1],
            "count": bucket["records"]["doc_count"],
        }
        for bucket in aggs.get("outgoing", {}).get("rels", {}).get("free", {})
        .get("types", {}).get("buckets", [])
    ]
    for source in aggs.get("incoming", {}).get("buckets", []):
        for bucket in source["rels"]["to_me"]["types"]["buckets"]:
            options.append({
                "relation_type": bucket["key"],
                "direction": "incoming",
                "target_type": source["key"],
                "count": bucket["records"]["doc_count"],
            })
    return options


async def outgoing_relation_target_ids(
    source_type: str,
    source_filter: dict[str, Any],
    relation_type: str,
    target_type: str,
    *,
    limit: int = 10000,
) -> tuple[list[str], bool]:
    """IDs that public `source_type` records matching `source_filter` point to.

    Resolves the incoming direction of a free relation without indexing it on the
    target (see search_service: outgoing only). Returns whether `limit` was exceeded.
    """
    es = get_es()
    result = await es.search(
        index=INDEX_NAME,
        body={
            "size": 0,
            "query": {"bool": {"filter": [
                {"term": {"record_type": source_type}},
                {"terms": {"status": list(PUBLIC_STATUSES)}},
                source_filter,
            ]}},
            "aggs": {"rels": {"nested": {"path": "adv_relations"}, "aggs": {"match": {
                "filter": {"bool": {"filter": [
                    {"exists": {"field": "adv_relations.direction"}},
                    {"term": {"adv_relations.relation_type": relation_type}},
                    {"term": {"adv_relations.target_type": target_type}},
                ]}},
                "aggs": {"ids": {"terms": {"field": "adv_relations.target_id", "size": limit + 1}}},
            }}}},
        },
    )
    buckets = (
        cast(dict[str, Any], result.body).get("aggregations", {}).get("rels", {})
        .get("match", {}).get("ids", {}).get("buckets", [])
    )
    ids = [str(bucket["key"]) for bucket in buckets]
    return ids[:limit], len(ids) > limit


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
        {"terms": {"status": list(PUBLIC_STATUSES)}},
        advanced_filter,
    ]
    result = await es.search(
        index=INDEX_NAME,
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
