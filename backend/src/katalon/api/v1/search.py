from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
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
    q: Annotated[str | None, Query(description="Full-text query")] = None,
    type: Annotated[str | None, Query(description="Filter by record_type")] = None,
    status: Annotated[str | None, Query(description="Filter by status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> SearchResponse:
    result = await search_service.search(
        query=q,
        record_type=type,
        status=status,
        page=page,
        page_size=page_size,
    )
    return SearchResponse(**result)


@router.post("/reindex", tags=["search"])
async def trigger_reindex() -> dict[str, str]:
    """Enqueue a full reindex Celery task."""
    from katalon.workers.index_tasks import reindex_all_task
    reindex_all_task.delay()
    return {"status": "queued"}
