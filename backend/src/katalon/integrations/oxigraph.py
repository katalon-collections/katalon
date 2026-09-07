# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import logging
from typing import Any

import httpx

from katalon.config import settings

logger = logging.getLogger(__name__)


class OxigraphError(Exception):
    """Base exception for Oxigraph triple store errors."""


class OxigraphConnectionError(OxigraphError):
    """Raised when Oxigraph cannot be reached."""


class OxigraphQueryError(OxigraphError):
    """Raised when a SPARQL query or update fails."""


class OxigraphClient:
    """Async client for Oxigraph HTTP server (Graph Store Protocol & SPARQL 1.1)."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 15.0,
    ) -> None:
        self.base_url = (base_url or settings.oxigraph_url).rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> OxigraphClient:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.close()

    async def health(self) -> bool:
        """Check whether Oxigraph is reachable and responsive."""
        try:
            client = await self._get_client()
            resp = await client.get("/")
            return resp.status_code == 200
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            logger.debug("Oxigraph healthcheck failed: %s", exc)
            return False

    async def put_graph(
        self,
        graph_uri: str,
        data: str | bytes,
        content_type: str = "text/turtle",
    ) -> None:
        """Store/replace triples in a named graph using the Graph Store HTTP Protocol."""
        client = await self._get_client()
        content = data.encode("utf-8") if isinstance(data, str) else data
        headers = {"Content-Type": content_type}
        params = {"graph": graph_uri}

        try:
            resp = await client.put("/store", params=params, content=content, headers=headers)
            if resp.status_code not in (200, 201, 204):
                raise OxigraphError(
                    f"Failed to put graph {graph_uri}: HTTP {resp.status_code} - {resp.text}"
                )
        except httpx.RequestError as exc:
            raise OxigraphConnectionError(
                f"Could not connect to Oxigraph at {self.base_url}: {exc}"
            ) from exc

    async def delete_graph(self, graph_uri: str) -> bool:
        """Delete a named graph. Returns True if deleted, False if graph did not exist (404)."""
        client = await self._get_client()
        params = {"graph": graph_uri}

        try:
            resp = await client.delete("/store", params=params)
            if resp.status_code in (200, 204):
                return True
            if resp.status_code == 404:
                return False
            raise OxigraphError(
                f"Failed to delete graph {graph_uri}: HTTP {resp.status_code} - {resp.text}"
            )
        except httpx.RequestError as exc:
            raise OxigraphConnectionError(
                f"Could not connect to Oxigraph at {self.base_url}: {exc}"
            ) from exc

    async def get_graph(
        self,
        graph_uri: str,
        accept: str = "text/turtle",
    ) -> str | None:
        """Fetch triples from a named graph. Returns content string or None if not found."""
        client = await self._get_client()
        params = {"graph": graph_uri}
        headers = {"Accept": accept}

        try:
            resp = await client.get("/store", params=params, headers=headers)
            if resp.status_code == 200:
                return resp.text
            if resp.status_code == 404:
                return None
            raise OxigraphError(
                f"Failed to get graph {graph_uri}: HTTP {resp.status_code} - {resp.text}"
            )
        except httpx.RequestError as exc:
            raise OxigraphConnectionError(
                f"Could not connect to Oxigraph at {self.base_url}: {exc}"
            ) from exc

    async def query(
        self,
        sparql: str,
        accept: str = "application/sparql-results+json",
        request_timeout: float | None = None,
        default_graph_uris: list[str] | None = None,
        named_graph_uris: list[str] | None = None,
    ) -> Any:
        """Execute a SPARQL query against /query.

        Returns parsed JSON dict for json accepts, or raw text for turtle/xml.
        """
        payload, _ = await self.query_raw(
            sparql=sparql,
            accept=accept,
            request_timeout=request_timeout,
            default_graph_uris=default_graph_uris,
            named_graph_uris=named_graph_uris,
        )
        if "json" in accept:
            import json
            return json.loads(payload.decode("utf-8"))
        return payload.decode("utf-8")

    async def query_raw(
        self,
        sparql: str,
        accept: str = "application/sparql-results+json",
        request_timeout: float | None = None,
        default_graph_uris: list[str] | None = None,
        named_graph_uris: list[str] | None = None,
    ) -> tuple[bytes, str]:
        """Execute a SPARQL query and return raw (content_bytes, content_type_header)."""
        client = await self._get_client()
        headers = {
            "Content-Type": "application/sparql-query",
            "Accept": accept,
        }
        params: list[tuple[str, str]] = []
        if default_graph_uris:
            for uri in default_graph_uris:
                params.append(("default-graph-uri", uri))
        else:
            params.append(("union-default-graph", ""))
        if named_graph_uris:
            for uri in named_graph_uris:
                params.append(("named-graph-uri", uri))

        kwargs: dict[str, Any] = {}
        if request_timeout is not None:
            kwargs["timeout"] = request_timeout
        if params:
            kwargs["params"] = params

        try:
            resp = await client.post(
                "/query",
                content=sparql.encode("utf-8"),
                headers=headers,
                **kwargs,
            )
            if resp.status_code != 200:
                raise OxigraphQueryError(
                    f"SPARQL query failed with HTTP {resp.status_code}: {resp.text}"
                )

            content_type = resp.headers.get("content-type", accept)
            return resp.content, content_type
        except httpx.TimeoutException as exc:
            raise OxigraphQueryError(
                f"SPARQL query timed out after {request_timeout}s: {exc}"
            ) from exc
        except httpx.RequestError as exc:
            raise OxigraphConnectionError(
                f"Could not connect to Oxigraph at {self.base_url}: {exc}"
            ) from exc
    async def update(
        self,
        sparql_update: str,
        request_timeout: float | None = None,
    ) -> None:
        """Execute a SPARQL update against /update."""
        client = await self._get_client()
        headers = {"Content-Type": "application/sparql-update"}
        kwargs: dict[str, Any] = {}
        if request_timeout is not None:
            kwargs["timeout"] = request_timeout

        try:
            resp = await client.post(
                "/update",
                content=sparql_update.encode("utf-8"),
                headers=headers,
                **kwargs,
            )
            if resp.status_code not in (200, 204):
                raise OxigraphQueryError(
                    f"SPARQL update failed with HTTP {resp.status_code}: {resp.text}"
                )
        except httpx.RequestError as exc:
            raise OxigraphConnectionError(
                f"Could not connect to Oxigraph at {self.base_url}: {exc}"
            ) from exc

    async def count_triples(self) -> int:
        """Return the total number of triples across all graphs (default + named)."""
        sparql = "SELECT (COUNT(*) AS ?count) WHERE { { ?s ?p ?o } UNION { GRAPH ?g { ?s ?p ?o } } }"
        res = await self.query(sparql, accept="application/sparql-results+json")
        try:
            bindings = res["results"]["bindings"]
            if bindings:
                return int(bindings[0]["count"]["value"])
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            logger.warning("Could not parse triple count from Oxigraph response: %s", exc)
        return 0

    async def clear_all(self) -> None:
        """Clear all triples in all graphs (default and named)."""
        await self.update("CLEAR ALL")


def get_oxigraph_client(base_url: str | None = None, timeout: float = 15.0) -> OxigraphClient:
    """Create a fresh OxigraphClient instance."""
    return OxigraphClient(base_url=base_url, timeout=timeout)


def validate_read_only_sparql(query_str: str) -> None:
    """Validate that query is syntactically valid SPARQL 1.1 Query (SELECT, CONSTRUCT, DESCRIBE, ASK).

    Rejects any SPARQL 1.1 Update operations (INSERT, DELETE, CLEAR, DROP, LOAD, etc.)
    or multiple chained statements.
    """
    from fastapi import HTTPException, status
    from pyparsing.exceptions import ParseException
    from rdflib.plugins.sparql.parser import parseQuery

    if not query_str or not query_str.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SPARQL query string cannot be empty.",
        )

    if len(query_str.encode("utf-8")) > settings.sparql_max_query_length:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"SPARQL query exceeds maximum length of {settings.sparql_max_query_length} bytes.",
        )

    try:
        parseQuery(query_str)
    except ParseException as exc:
        logger.debug("SPARQL query parse rejection: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or unauthorized SPARQL query: {exc.msg} (line {exc.lineno}, col {exc.col})",
        ) from exc
    except Exception as exc:
        logger.debug("SPARQL query validation error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid SPARQL query syntax.",
        ) from exc
