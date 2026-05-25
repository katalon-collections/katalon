from __future__ import annotations

from typing import Any

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
        }
    },
}

INDEX_NAME = "katalon_records"
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
    ops: list[dict] = []
    for doc_id, body in records:
        ops.append({"index": {"_index": INDEX_NAME, "_id": doc_id}})
        ops.append(body)
    resp = await es.bulk(body=ops, refresh=True)
    errors = [item for item in resp["items"] if "error" in item.get("index", {})]
    return len(records) - len(errors)


async def index_document(doc_id: str, body: dict[str, Any]) -> None:
    es = get_es()
    await es.index(index=INDEX_NAME, id=doc_id, body=body, refresh=True)


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
    extra_filters: dict[str, str] | None = None,
    facet_fields: list[str] | None = None,
    rel_filters: dict[str, str] | None = None,
) -> dict[str, Any]:
    es = get_es()

    must: list[dict] = []
    filters: list[dict] = []

    if query:
        must.append({
            "query_string": {
                "query": query,
                "fields": ["title^3", "search_text^2"],
                "default_operator": "AND",
                "lenient": True,
                "allow_leading_wildcard": False,
            }
        })
    else:
        must.append({"match_all": {}})

    if record_type:
        filters.append({"term": {"record_type": record_type}})
    if status:
        filters.append({"term": {"status": status}})
    for field, value in (extra_filters or {}).items():
        filters.append({"term": {f"facet_{field}": value}})
    for field, value in (rel_filters or {}).items():
        filters.append({"term": {field: value}})

    es_query: dict[str, Any] = {"bool": {"must": must, "filter": filters}}

    aggs: dict[str, Any] = {
        "by_type":             {"terms": {"field": "record_type", "size": 10}},
        "by_status":           {"terms": {"field": "status", "size": 10}},
        "related_entities":    {"terms": {"field": "related_entities", "size": 30}},
        "related_places":      {"terms": {"field": "related_places", "size": 30}},
        "related_occurrences": {"terms": {"field": "related_occurrences", "size": 30}},
    }
    for field in facet_fields or []:
        aggs[f"meta_{field}"] = {"terms": {"field": f"facet_{field}", "size": 20}}

    result = await es.search(
        index=INDEX_NAME,
        body={"query": es_query, "aggs": aggs, "from": from_, "size": size},
    )
    return result.body
