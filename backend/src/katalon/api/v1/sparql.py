# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""SPARQL 1.1 Protocol Endpoint (read-only) for querying the RDF projection.

Supports:
- GET /v1/sparql?query=...
- POST /v1/sparql (Content-Type: application/x-www-form-urlencoded with query=...)
- POST /v1/sparql (Content-Type: application/sparql-query with raw SPARQL body)

Enforces:
- Feature gate (oxigraph_enabled and sparql_endpoint_enabled)
- Read-only validation (rejects updates/inserts/drops via AST parsing)
- Authorization (JWT or API-Key, unless sparql_require_auth is False)
- Query timeouts and size limits
- Rate limiting
"""

from __future__ import annotations

import datetime
import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from katalon.config import settings
from katalon.core.dependencies import (
    CurrentUser,
    DBDep,
    OptionalCurrentUser,
    require_role,
)
from katalon.core.limiter import limiter
from katalon.core.models import SavedSparqlQuery
from katalon.integrations.oxigraph import (
    OxigraphConnectionError,
    OxigraphQueryError,
    get_oxigraph_client,
    validate_read_only_sparql,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sparql"])

# Supported standard Accept MIME types
DEFAULT_ACCEPT = "application/sparql-results+json"


class SparqlStatusResponse(BaseModel):
    enabled: bool
    reachable: bool
    triples_count: int | None = None
    endpoint_url: str = "/sparql"
    require_auth: bool = True
    query_timeout: float = 30.0


class SavedSparqlQueryCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=256)
    description: str | None = None
    query: str = Field(..., min_length=1)
    tags: list[str] = Field(default_factory=list)
    is_shared: bool = True


class SavedSparqlQueryUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=256)
    description: str | None = None
    query: str | None = Field(None, min_length=1)
    tags: list[str] | None = None
    is_shared: bool | None = None


class SavedSparqlQueryRead(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None = None
    query: str
    tags: list[Any] = Field(default_factory=list)
    is_shared: bool = True
    created_by: uuid.UUID | None = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class NL2SparqlRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)


class NL2SparqlResponse(BaseModel):
    sparql: str
    explanation: str | None = None
ALLOWED_ACCEPT_PREFIXES = (
    "application/sparql-results+json",
    "application/sparql-results+xml",
    "application/json",
    "text/csv",
    "text/tab-separated-values",
    "text/turtle",
    "application/ld+json",
    "application/n-triples",
    "application/rdf+xml",
    "*/*",
)



def resolve_accept_header(accept_header: str | None) -> str:
    """Choose best supported Accept header for Oxigraph."""
    if not accept_header or accept_header == "*/*":
        return DEFAULT_ACCEPT

    # Check for direct match or preference
    for candidate in accept_header.split(","):
        mime = candidate.split(";")[0].strip().lower()
        for allowed in ALLOWED_ACCEPT_PREFIXES:
            if allowed != "*/*" and mime == allowed:
                return mime

    return DEFAULT_ACCEPT


def check_sparql_access(user: OptionalCurrentUser) -> None:
    """Ensure service is enabled and caller is authorized."""
    if not settings.oxigraph_enabled or not settings.sparql_endpoint_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SPARQL endpoint is disabled.",
        )

    if settings.sparql_require_auth and user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to access SPARQL endpoint.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def execute_sparql_query(
    query_str: str,
    accept: str,
    default_graph_uris: list[str] | None = None,
    named_graph_uris: list[str] | None = None,
) -> Response:
    """Validate and execute query against Oxigraph."""
    validate_read_only_sparql(query_str)

    client = get_oxigraph_client(timeout=settings.sparql_query_timeout + 5.0)
    try:
        content_bytes, content_type = await client.query_raw(
            sparql=query_str,
            accept=accept,
            request_timeout=settings.sparql_query_timeout,
            default_graph_uris=default_graph_uris,
            named_graph_uris=named_graph_uris,
        )
        return Response(content=content_bytes, media_type=content_type)
    except OxigraphQueryError as exc:
        err_msg = str(exc)
        if "timed out" in err_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=f"SPARQL query timed out after {settings.sparql_query_timeout}s.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"SPARQL execution error: {exc}",
        ) from exc
    except OxigraphConnectionError as exc:
        logger.error("Could not reach triple store: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not reach RDF triple store.",
        ) from exc
    finally:
        await client.close()

@router.get(
    "/sparql/status",
    response_model=SparqlStatusResponse,
    dependencies=[require_role("admin")],
    summary="Get status and triple count of the RDF projection",
)
@router.get(
    "/v1/sparql/status",
    response_model=SparqlStatusResponse,
    dependencies=[require_role("admin")],
    include_in_schema=False,
)
async def sparql_status() -> SparqlStatusResponse:
    """Get status and triple count of the RDF projection (Admin only)."""
    if not settings.oxigraph_enabled:
        return SparqlStatusResponse(
            enabled=False,
            reachable=False,
            triples_count=None,
            endpoint_url="/sparql",
            require_auth=settings.sparql_require_auth,
            query_timeout=settings.sparql_query_timeout,
        )

    client = get_oxigraph_client(timeout=5.0)
    reachable = False
    triples_count: int | None = None
    try:
        reachable = await client.health()
        if reachable:
            try:
                triples_count = await client.count_triples()
            except Exception as exc:
                logger.warning("Failed to count triples in Oxigraph: %s", exc)
    finally:
        await client.close()

    return SparqlStatusResponse(
        enabled=True,
        reachable=reachable,
        triples_count=triples_count,
        endpoint_url="/sparql",
        require_auth=settings.sparql_require_auth,
        query_timeout=settings.sparql_query_timeout,
    )


@router.post(
    "/sparql/rebuild",
    dependencies=[require_role("admin")],
    summary="Trigger a full rebuild of the RDF triple store from PostgreSQL",
    responses={
        401: {"description": "Missing, invalid, or expired credentials"},
        403: {"description": "Insufficient permissions"},
        503: {"description": "Oxigraph or task queue unavailable"},
    },
)
@router.post(
    "/v1/sparql/rebuild",
    dependencies=[require_role("admin")],
    include_in_schema=False,
)
async def sparql_rebuild() -> dict[str, str]:
    """Trigger a full asynchronous rebuild of all named graphs in Oxigraph (Admin only)."""
    if not settings.oxigraph_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SPARQL / Oxigraph integration is disabled.",
        )
    from katalon.workers.enqueue import enqueue_or_503
    from katalon.workers.rdf_tasks import rebuild_rdf_all_task

    enqueue_or_503(rebuild_rdf_all_task)
    return {"status": "queued"}


@router.get(
    "/sparql",
    summary="Execute a SPARQL 1.1 read-only query (GET)",
    response_class=Response,
)
@router.get(
    "/v1/sparql",
    response_class=Response,
    include_in_schema=False,
)
@limiter.limit(lambda: settings.rate_limit_sparql)
async def sparql_get(
    request: Request,
    user: OptionalCurrentUser,
    query: Annotated[str, Query(description="SPARQL 1.1 Query")],
    default_graph_uri: Annotated[
        list[str] | None,
        Query(alias="default-graph-uri", description="Default graph URIs"),
    ] = None,
    named_graph_uri: Annotated[
        list[str] | None,
        Query(alias="named-graph-uri", description="Named graph URIs"),
    ] = None,
) -> Response:
    """SPARQL 1.1 Protocol GET query execution."""
    check_sparql_access(user)
    accept = resolve_accept_header(request.headers.get("accept"))
    return await execute_sparql_query(
        query_str=query,
        accept=accept,
        default_graph_uris=default_graph_uri,
        named_graph_uris=named_graph_uri,
    )


@router.post(
    "/sparql",
    summary="Execute a SPARQL 1.1 read-only query (POST)",
    response_class=Response,
)
@router.post(
    "/v1/sparql",
    response_class=Response,
    include_in_schema=False,
)
@limiter.limit(lambda: settings.rate_limit_sparql)
async def sparql_post(
    request: Request,
    user: OptionalCurrentUser,
    default_graph_uri: Annotated[
        list[str] | None,
        Query(alias="default-graph-uri", description="Default graph URIs"),
    ] = None,
    named_graph_uri: Annotated[
        list[str] | None,
        Query(alias="named-graph-uri", description="Named graph URIs"),
    ] = None,
) -> Response:
    """SPARQL 1.1 Protocol POST query execution.

    Supports both application/x-www-form-urlencoded (with query parameter)
    and application/sparql-query (raw SPARQL in request body).
    """
    check_sparql_access(user)
    content_type = request.headers.get("content-type", "").lower().split(";")[0].strip()

    query_str = ""
    if content_type == "application/x-www-form-urlencoded":
        form_data = await request.form()
        query_val = form_data.get("query")
        if not isinstance(query_val, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing 'query' parameter in form-encoded POST body.",
            )
        query_str = query_val
        # Also check for form-specified graphs if not in query params
        if not default_graph_uri:
            default_graphs = form_data.getlist("default-graph-uri")
            if default_graphs:
                default_graph_uri = [str(g) for g in default_graphs]
        if not named_graph_uri:
            named_graphs = form_data.getlist("named-graph-uri")
            if named_graphs:
                named_graph_uri = [str(g) for g in named_graphs]
    elif content_type == "application/sparql-query":
        body_bytes = await request.body()
        try:
            query_str = body_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Request body is not valid UTF-8.",
            ) from exc
    else:
        # If Content-Type is missing or unsupported
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported Content-Type '{content_type}'. Must be 'application/sparql-query' or 'application/x-www-form-urlencoded'.",
        )

    accept = resolve_accept_header(request.headers.get("accept"))
    return await execute_sparql_query(
        query_str=query_str,
        accept=accept,
        default_graph_uris=default_graph_uri,
        named_graph_uris=named_graph_uri,
    )


# ---------------------------------------------------------------------------
# Saved SPARQL Queries CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/v1/sparql/queries",
    response_model=list[SavedSparqlQueryRead],
    dependencies=[require_role("admin")],
    summary="List saved SPARQL queries",
)
@router.get(
    "/sparql/queries",
    response_model=list[SavedSparqlQueryRead],
    dependencies=[require_role("admin")],
    include_in_schema=False,
)
async def list_saved_sparql_queries(
    db: DBDep,
    tag: Annotated[str | None, Query(description="Filter by tag")] = None,
    q: Annotated[str | None, Query(description="Search in title or description")] = None,
) -> list[SavedSparqlQuery]:
    """List all saved SPARQL queries with optional tag or text search (Admin only)."""
    if not settings.oxigraph_enabled or not settings.sparql_endpoint_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SPARQL endpoint is disabled.",
        )
    stmt = select(SavedSparqlQuery).order_by(SavedSparqlQuery.updated_at.desc())
    result = await db.execute(stmt)
    queries = list(result.scalars().all())
    if tag:
        queries = [item for item in queries if tag in (item.tags or [])]
    if q:
        search_lower = q.lower()
        queries = [
            item
            for item in queries
            if search_lower in item.title.lower()
            or (item.description and search_lower in item.description.lower())
        ]
    return queries


@router.post(
    "/v1/sparql/queries",
    response_model=SavedSparqlQueryRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_role("admin")],
    summary="Create a saved SPARQL query",
)
@router.post(
    "/sparql/queries",
    response_model=SavedSparqlQueryRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_role("admin")],
    include_in_schema=False,
)
async def create_saved_sparql_query(
    data: SavedSparqlQueryCreate,
    db: DBDep,
    current_user: CurrentUser,
) -> SavedSparqlQuery:
    """Create a new saved SPARQL query (Admin only)."""
    if not settings.oxigraph_enabled or not settings.sparql_endpoint_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SPARQL endpoint is disabled.",
        )
    validate_read_only_sparql(data.query)
    now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
    saved = SavedSparqlQuery(
        id=uuid.uuid4(),
        title=data.title.strip(),
        description=data.description.strip() if data.description else None,
        query=data.query.strip(),
        tags=data.tags,
        is_shared=data.is_shared,
        created_by=current_user.id if current_user else None,
        created_at=now,
        updated_at=now,
    )
    db.add(saved)
    await db.commit()
    await db.refresh(saved)
    return saved


@router.get(
    "/v1/sparql/queries/{query_id}",
    response_model=SavedSparqlQueryRead,
    dependencies=[require_role("admin")],
    summary="Get a saved SPARQL query by ID",
)
@router.get(
    "/sparql/queries/{query_id}",
    response_model=SavedSparqlQueryRead,
    dependencies=[require_role("admin")],
    include_in_schema=False,
)
async def get_saved_sparql_query(
    query_id: uuid.UUID,
    db: DBDep,
) -> SavedSparqlQuery:
    """Get a single saved SPARQL query by ID (Admin only)."""
    if not settings.oxigraph_enabled or not settings.sparql_endpoint_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SPARQL endpoint is disabled.",
        )
    result = await db.execute(select(SavedSparqlQuery).where(SavedSparqlQuery.id == query_id))
    saved = result.scalar_one_or_none()
    if not saved:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved SPARQL query not found.",
        )
    return saved


@router.put(
    "/v1/sparql/queries/{query_id}",
    response_model=SavedSparqlQueryRead,
    dependencies=[require_role("admin")],
    summary="Update a saved SPARQL query",
)
@router.put(
    "/sparql/queries/{query_id}",
    response_model=SavedSparqlQueryRead,
    dependencies=[require_role("admin")],
    include_in_schema=False,
)
async def update_saved_sparql_query(
    query_id: uuid.UUID,
    data: SavedSparqlQueryUpdate,
    db: DBDep,
) -> SavedSparqlQuery:
    """Update a saved SPARQL query (Admin only)."""
    if not settings.oxigraph_enabled or not settings.sparql_endpoint_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SPARQL endpoint is disabled.",
        )
    result = await db.execute(select(SavedSparqlQuery).where(SavedSparqlQuery.id == query_id))
    saved = result.scalar_one_or_none()
    if not saved:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved SPARQL query not found.",
        )

    if data.query is not None:
        validate_read_only_sparql(data.query)
        saved.query = data.query.strip()
    if data.title is not None:
        saved.title = data.title.strip()
    if data.description is not None:
        saved.description = data.description.strip() if data.description else None
    if data.tags is not None:
        saved.tags = data.tags
    if data.is_shared is not None:
        saved.is_shared = data.is_shared

    await db.commit()
    await db.refresh(saved)
    return saved


@router.delete(
    "/v1/sparql/queries/{query_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[require_role("admin")],
    summary="Delete a saved SPARQL query",
)
@router.delete(
    "/sparql/queries/{query_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[require_role("admin")],
    include_in_schema=False,
)
async def delete_saved_sparql_query(
    query_id: uuid.UUID,
    db: DBDep,
) -> None:
    """Delete a saved SPARQL query by ID (Admin only)."""
    if not settings.oxigraph_enabled or not settings.sparql_endpoint_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SPARQL endpoint is disabled.",
        )
    result = await db.execute(select(SavedSparqlQuery).where(SavedSparqlQuery.id == query_id))
    saved = result.scalar_one_or_none()
    if not saved:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved SPARQL query not found.",
        )
    await db.delete(saved)
    await db.commit()


# ---------------------------------------------------------------------------
# Natural Language to SPARQL (NL2SPARQL)
# ---------------------------------------------------------------------------


@router.post(
    "/v1/sparql/nl2sparql",
    response_model=NL2SparqlResponse,
    dependencies=[require_role("admin")],
    summary="Translate natural language to SPARQL query via LLM",
)
@router.post(
    "/sparql/nl2sparql",
    response_model=NL2SparqlResponse,
    dependencies=[require_role("admin")],
    include_in_schema=False,
)
async def nl2sparql_endpoint(
    data: NL2SparqlRequest,
    db: DBDep,
    current_user: CurrentUser,
) -> NL2SparqlResponse:
    """Translate a natural language prompt into a read-only SPARQL query (Admin only)."""
    if not settings.oxigraph_enabled or not settings.sparql_endpoint_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SPARQL endpoint is disabled.",
        )
    from katalon.services.sparql_ai_service import generate_sparql_from_prompt

    res = await generate_sparql_from_prompt(db, current_user.id, data.prompt)
    return NL2SparqlResponse(sparql=res["sparql"], explanation=res.get("explanation"))
