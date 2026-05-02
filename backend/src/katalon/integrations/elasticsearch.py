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


async def ensure_index() -> None:
    es = get_es()
    exists = await es.indices.exists(index=INDEX_NAME)
    if not exists:
        await es.indices.create(index=INDEX_NAME, body=INDEX_SETTINGS)


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
) -> dict[str, Any]:
    es = get_es()

    must: list[dict] = []
    filters: list[dict] = []

    if query:
        must.append({"multi_match": {"query": query, "fields": ["title^3", "search_text^2", "metadata.*"], "type": "best_fields"}})
    else:
        must.append({"match_all": {}})

    if record_type:
        filters.append({"term": {"record_type": record_type}})
    if status:
        filters.append({"term": {"status": status}})

    es_query: dict[str, Any] = {
        "bool": {
            "must": must,
            "filter": filters,
        }
    }

    aggs: dict[str, Any] = {
        "by_type":   {"terms": {"field": "record_type", "size": 10}},
        "by_status": {"terms": {"field": "status", "size": 10}},
    }

    result = await es.search(
        index=INDEX_NAME,
        body={"query": es_query, "aggs": aggs, "from": from_, "size": size},
    )
    return result.body
