from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, cast

from elasticsearch import AsyncElasticsearch, NotFoundError

from katalon.config import settings


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
            "record_type":         {"type": "keyword"},
            "title":               {"type": "text", "analyzer": "katalon_default", "fields": {"raw": {"type": "keyword"}}},
            "status":              {"type": "keyword"},
            "metadata":            {"type": "object", "enabled": False},
            "search_text":         {"type": "text", "analyzer": "katalon_default"},
            "created_at":          {"type": "date"},
            "updated_at":          {"type": "date"},
            "related_entities":    {"type": "keyword"},
            "related_places":      {"type": "keyword"},
            "related_occurrences": {"type": "keyword"},
            "adv_fields": {
                "type": "nested",
                "properties": {
                    "name":          {"type": "keyword"},
                    "text_value":    {"type": "text", "analyzer": "katalon_default"},
                    "keyword_value": {"type": "keyword"},
                    "number_value":  {"type": "double"},
                    "date_min":      {"type": "long"},
                    "date_max":      {"type": "long"},
                    "bool_value":    {"type": "boolean"},
                },
            },
            "adv_relations": {
                "type": "nested",
                "properties": {
                    "source_field": {"type": "keyword"},
                    "target_type":  {"type": "keyword"},
                    "target_id":    {"type": "keyword"},
                    "relation_type": {"type": "keyword"},
                },
            },
        }
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


async def reindex_type(target_type: str, records: list[tuple[str, dict[str, Any]]]) -> int:
    """Delete all docs of target_type and re-index the supplied records.

    Returns the number of documents indexed.
    """
    es = get_es()
    # Delete existing docs for this type
    await es.delete_by_query(
        index=INDEX_NAME,
        body={"query": {"term": {"record_type": target_type}}},
        refresh=True,
    )
    if not records:
        return 0
    ops: list[dict[str, Any]] = []
    for doc_id, body in records:
        ops.append({"index": {"_index": INDEX_NAME, "_id": doc_id}})
        ops.append(body)
    resp = await es.bulk(body=ops, refresh=True)
    errors = [item for item in resp["items"] if "error" in item.get("index", {})]
    return len(records) - len(errors)


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
    rel_filters: dict[str, str] | None = None,
    active_objects_only: bool = False,
    record_types: tuple[str, ...] | None = None,
    advanced_filter: dict[str, Any] | None = None,
    facet_sort: str = "count",
) -> dict[str, Any]:
    es = get_es()

    must: list[dict[str, Any]] = []
    filters: list[dict[str, Any]] = []

    if query:
        q = query.strip()
        # Add trailing wildcard for prefix/autocomplete unless query already has operators
        if q and not any(c in q for c in (':', '"', '*', '?', '+', '-', '~', '(')):
            q = q + '*'
        must.append({
            "query_string": {
                "query": q,
                "fields": ["title^3", "search_text^2"],
                "default_operator": "AND",
                "lenient": True,
                "allow_leading_wildcard": True,
            }
        })
    else:
        must.append({"match_all": {}})

    if record_type:
        filters.append({"term": {"record_type": record_type}})
    elif record_types:
        filters.append({"terms": {"record_type": list(record_types)}})
    if status:
        filters.append({"term": {"status": status}})
    facet_filters = {
        field: (
            {"term": {f"facet_{field}": values[0]}}
            if len(values) == 1
            else {"terms": {f"facet_{field}": values}}
        )
        for field, values in (extra_filters or {}).items()
        if values
    }
    numeric_facet_filters = {
        field: {"range": {f"number_facet_{field}": {
            key: value for key, value in {"gte": lower, "lte": upper}.items() if value is not None
        }}}
        for field, (lower, upper) in (numeric_filters or {}).items()
        if lower is not None or upper is not None
    }
    for field, value in (rel_filters or {}).items():
        filters.append({"term": {field: value}})
    if active_objects_only:
        filters.append({
            "bool": {
                "should": [
                    {"bool": {"must_not": {"term": {"record_type": "object"}}}},
                    {"term": {"collection_status": "active"}},
                ],
                "minimum_should_match": 1,
            }
        })
    if advanced_filter:
        filters.append(advanced_filter)

    base_filters = list(filters)
    filters.extend(facet_filters.values())
    filters.extend(numeric_facet_filters.values())

    es_query: dict[str, Any] = {"bool": {"must": must, "filter": filters}}

    aggs: dict[str, Any] = {
        "by_type":             {"terms": {"field": "record_type", "size": 10}},
        "by_status":           {"terms": {"field": "status", "size": 10}},
        "related_entities":    {"terms": {"field": "related_entities", "size": 30}},
        "related_places":      {"terms": {"field": "related_places", "size": 30}},
        "related_occurrences": {"terms": {"field": "related_occurrences", "size": 30}},
    }
    # Fetch generously beyond the portal's initially visible count so "show
    # more" can reveal further values without a second round-trip.
    facet_order = {"_key": "asc"} if facet_sort == "alpha" else {"_count": "desc"}
    for field in facet_fields or []:
        aggregation_filters = [
            value for name, value in facet_filters.items() if name != field
        ]
        aggs[f"meta_{field}"] = {
            "global": {},
            "aggs": {
                "filtered": {
                    "filter": {"bool": {"must": must, "filter": [
                        *base_filters,
                        *aggregation_filters,
                    ]}},
                    "aggs": {
                        "values": {"terms": {"field": f"facet_{field}", "size": 100, "order": facet_order}}
                    },
                }
            },
        }
        numeric_aggregation_filters = [
            value for name, value in numeric_facet_filters.items() if name != field
        ]
        aggs[f"numeric_{field}"] = {
            "global": {},
            "aggs": {
                "filtered": {
                    "filter": {"bool": {"must": must, "filter": [
                        *base_filters,
                        *facet_filters.values(),
                        *numeric_aggregation_filters,
                    ]}},
                    "aggs": {
                        "values": {
                            "stats": {"field": f"number_facet_{field}"}
                        }
                    },
                }
            },
        }

    result = await es.search(
        index=INDEX_NAME,
        body={"query": es_query, "aggs": aggs, "from": from_, "size": size},
    )
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
    if record_type == "object":
        filters.append({"term": {"collection_status": "active"}})
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
