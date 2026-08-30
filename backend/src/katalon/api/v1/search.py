from __future__ import annotations

import math
from typing import Annotated

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from katalon.core.dependencies import OptionalCurrentUser, require_role
from katalon.core.limiter import limiter
from katalon.services import search_service

router = APIRouter(prefix="/search", tags=["search"])


class FacetBucket(BaseModel):
    value: str
    count: int


class NumericFacetBounds(BaseModel):
    min: float
    max: float


class SearchResult(BaseModel):
    id: str
    record_type: str
    title: str
    status: str | None = None
    score: float | None = None
    subtitle_values: dict[str, str | list[str]] | None = None


class SearchResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[SearchResult]
    facets: dict[str, list[FacetBucket]]
    numeric_facets: dict[str, NumericFacetBounds] = Field(default_factory=dict)


def _range_filters(request: Request) -> dict[str, tuple[float | None, float | None]]:
    values: dict[str, dict[str, float]] = {}
    for key, value in request.query_params.multi_items():
        if not key.startswith("range_") or not key.endswith(("_from", "_to")):
            continue
        field, bound = key[6:].rsplit("_", 1)
        try:
            number = float(value)
        except ValueError as exc:
            raise ValueError("Zahlengrenzen müssen gültige Zahlen sein.") from exc
        if not math.isfinite(number):
            raise ValueError("Zahlengrenzen müssen endliche Zahlen sein.")
        values.setdefault(field, {})[bound] = number
    result = {
        field: (bounds.get("from"), bounds.get("to"))
        for field, bounds in values.items()
    }
    if any(lower is not None and upper is not None and lower > upper for lower, upper in result.values()):
        raise ValueError("Die untere Zahlengrenze muss vor der oberen liegen.")
    return result


@router.get(
    "",
    response_model=SearchResponse,
    summary="Search records with filters and facets",
)
@limiter.limit("100/minute")
async def search(
    request: Request,
    current_user: OptionalCurrentUser,
    q: Annotated[str | None, Query(description="Full-text query")] = None,
    type: Annotated[str | None, Query(description="Filter by record_type")] = None,
    status: Annotated[str | None, Query(description="Filter by status")] = None,
    facets: Annotated[str | None, Query(description="Comma-separated metadata fields to aggregate")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    rel_entity: Annotated[str | None, Query(description="Filter objects by related entity name")] = None,
    rel_place: Annotated[str | None, Query(description="Filter objects by related place name")] = None,
    rel_occurrence: Annotated[str | None, Query(description="Filter objects by related occurrence name")] = None,
) -> SearchResponse:
    # Unauthenticated callers may only see public records
    if current_user is None and not status:
        status = "public"

    # Extra metadata filters: any query param starting with "meta_"
    extra_filters: dict[str, list[str]] = {
        key[5:]: [value for value in request.query_params.getlist(key) if value]
        for key in request.query_params.keys()
        if key.startswith("meta_")
    }
    facet_fields = [f.strip() for f in facets.split(",") if f.strip()] if facets else []
    rel_filters: dict[str, str] = {}
    active_objects_only = current_user is None
    if rel_entity:
        rel_filters["related_entities"] = rel_entity
    if rel_place:
        rel_filters["related_places"] = rel_place
    if rel_occurrence:
        rel_filters["related_occurrences"] = rel_occurrence
    try:
        numeric_filters = _range_filters(request)
    except ValueError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result = await search_service.search(
        query=q,
        record_type=type,
        status=status,
        page=page,
        page_size=page_size,
        extra_filters=extra_filters or None,
        numeric_filters=numeric_filters or None,
        facet_fields=facet_fields or None,
        rel_filters=rel_filters or None,
        active_objects_only=active_objects_only,
    )
    return SearchResponse(**result)


@router.post(
    "/reindex",
    dependencies=[require_role("admin")],
    summary="Trigger a full search index rebuild",
    responses={
        403: {"description": "Insufficient permissions"},
        503: {"description": "Background task queue unavailable (broker down)"},
    },
)
async def trigger_reindex() -> dict[str, str]:
    from katalon.workers.enqueue import enqueue_or_503
    from katalon.workers.index_tasks import reindex_all_task
    enqueue_or_503(reindex_all_task)
    return {"status": "queued"}


@router.post(
    "/reindex/{target_type}",
    dependencies=[require_role("admin")],
    summary="Trigger a search index rebuild for one record type",
    responses={
        403: {"description": "Insufficient permissions"},
        422: {"description": "Invalid target type"},
        503: {"description": "Background task queue unavailable (broker down)"},
    },
)
async def trigger_reindex_type(target_type: str) -> dict[str, str]:
    valid = {"object", "entity", "place", "occurrence", "procedure"}
    if target_type not in valid:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail=f"Ungültiger Typ. Erlaubt: {', '.join(sorted(valid))}")
    from katalon.workers.enqueue import enqueue_or_503
    from katalon.workers.index_tasks import bulk_reindex_type_task
    enqueue_or_503(bulk_reindex_type_task, target_type)
    return {"status": "queued", "target_type": target_type}
