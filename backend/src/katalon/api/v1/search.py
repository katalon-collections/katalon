from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from katalon.services import search_service

router = APIRouter(prefix="/search", tags=["search"])


class FacetBucket(BaseModel):
    value: str
    count: int


class SearchResult(BaseModel):
    id: str
    record_type: str
    title: str
    status: str | None = None
    score: float | None = None


class SearchResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[SearchResult]
    facets: dict[str, list[FacetBucket]]


@router.get("", response_model=SearchResponse)
async def search(
    request: Request,
    q: Annotated[str | None, Query(description="Full-text query")] = None,
    type: Annotated[str | None, Query(description="Filter by record_type")] = None,
    status: Annotated[str | None, Query(description="Filter by status")] = None,
    facets: Annotated[str | None, Query(description="Comma-separated metadata fields to aggregate")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> SearchResponse:
    # Extra metadata filters: any query param starting with "meta_"
    extra_filters: dict[str, str] = {
        k[5:]: v
        for k, v in request.query_params.items()
        if k.startswith("meta_") and v
    }
    facet_fields = [f.strip() for f in facets.split(",") if f.strip()] if facets else []
    result = await search_service.search(
        query=q,
        record_type=type,
        status=status,
        page=page,
        page_size=page_size,
        extra_filters=extra_filters or None,
        facet_fields=facet_fields or None,
    )
    return SearchResponse(**result)


@router.post("/reindex", tags=["search"])
async def trigger_reindex() -> dict[str, str]:
    """Enqueue a full reindex Celery task (all types)."""
    from katalon.workers.index_tasks import reindex_all_task
    reindex_all_task.delay()
    return {"status": "queued"}


@router.post("/reindex/{target_type}", tags=["search"])
async def trigger_reindex_type(target_type: str) -> dict[str, str]:
    """Enqueue a type-specific reindex (e.g. after schema changes)."""
    valid = {"object", "entity", "place", "occurrence"}
    if target_type not in valid:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail=f"Ungültiger Typ. Erlaubt: {', '.join(sorted(valid))}")
    from katalon.workers.index_tasks import bulk_reindex_type_task
    bulk_reindex_type_task.delay(target_type)
    return {"status": "queued", "target_type": target_type}
