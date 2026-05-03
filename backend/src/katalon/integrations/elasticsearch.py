from __future__ import annotations

from typing import Any

from elasticsearch import AsyncElasticsearch, NotFoundError

from katalon.config import settings

_client: AsyncElasticsearch | None = None


def get_es() -> AsyncElasticsearch:
    global _client
    if _client is None:
        _client = AsyncElasticsearch(settings.elasticsearch_url)
    return _client


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
        "properties": {
            "record_type": {"type": "keyword"},
            "title":       {"type": "text", "analyzer": "katalon_default", "fields": {"raw": {"type": "keyword"}}},
            "status":      {"type": "keyword"},
            "metadata":    {"type": "object", "dynamic": True},
            "search_text": {"type": "text", "analyzer": "katalon_default"},
            "created_at":  {"type": "date"},
            "updated_at":  {"type": "date"},
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
    await es.index(index=INDEX_NAME, id=doc_id, body=body)


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
) -> dict[str, Any]:
    es = get_es()

    must: list[dict] = []
    filters: list[dict] = []

    if query:
        # Use query_string with wildcard on metadata fields, but exclude date fields
        # to avoid parsing text as dates. search_text already contains all text values.
        must.append({
            "multi_match": {
                "query": query,
                "fields": ["title^3", "search_text^2"],
                "type": "best_fields",
                "lenient": True,
            }
        })
    else:
        must.append({"match_all": {}})

    if record_type:
        filters.append({"term": {"record_type": record_type}})
    if status:
        filters.append({"term": {"status": status}})
    for field, value in (extra_filters or {}).items():
        filters.append({"term": {f"metadata.{field}.keyword": value}})

    es_query: dict[str, Any] = {"bool": {"must": must, "filter": filters}}

    aggs: dict[str, Any] = {
        "by_type":   {"terms": {"field": "record_type", "size": 10}},
        "by_status": {"terms": {"field": "status", "size": 10}},
    }
    for field in facet_fields or []:
        aggs[f"meta_{field}"] = {"terms": {"field": f"metadata.{field}.keyword", "size": 20}}

    result = await es.search(
        index=INDEX_NAME,
        body={"query": es_query, "aggs": aggs, "from": from_, "size": size},
    )
    return result.body
