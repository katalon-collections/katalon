# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

from typing import Any

import httpx
import pytest

from katalon.integrations.oxigraph import (
    OxigraphClient,
    OxigraphConnectionError,
    OxigraphError,
    OxigraphQueryError,
)


def _client_with_transport(handler: Any) -> OxigraphClient:
    transport = httpx.MockTransport(handler)
    client = OxigraphClient(base_url="http://oxigraph.test:7878")
    client._client = httpx.AsyncClient(
        base_url="http://oxigraph.test:7878",
        transport=transport,
    )
    return client


@pytest.mark.asyncio
async def test_health_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/"
        return httpx.Response(200, text="OK")

    client = _client_with_transport(handler)
    assert await client.health() is True
    await client.close()


@pytest.mark.asyncio
async def test_health_failure_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Error")

    client = _client_with_transport(handler)
    assert await client.health() is False
    await client.close()


@pytest.mark.asyncio
async def test_health_connection_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Failed to connect")

    client = _client_with_transport(handler)
    assert await client.health() is False
    await client.close()


@pytest.mark.asyncio
async def test_put_graph_success() -> None:
    recorded_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        return httpx.Response(204)

    client = _client_with_transport(handler)
    graph_uri = "https://katalon.example.org/objects/123"
    turtle_data = "<https://katalon.example.org/objects/123> a <http://example.org/Object> ."

    await client.put_graph(graph_uri, turtle_data)
    assert len(recorded_requests) == 1
    req = recorded_requests[0]
    assert req.method == "PUT"
    assert req.url.path == "/store"
    assert req.url.params["graph"] == graph_uri
    assert req.headers["Content-Type"] == "text/turtle"
    assert req.content == turtle_data.encode("utf-8")
    await client.close()


@pytest.mark.asyncio
async def test_put_graph_error_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="Bad Request syntax")

    client = _client_with_transport(handler)
    with pytest.raises(OxigraphError, match="Failed to put graph"):
        await client.put_graph("http://example.org/g", "invalid data")
    await client.close()


@pytest.mark.asyncio
async def test_delete_graph_exists() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.url.path == "/store"
        assert request.url.params["graph"] == "http://example.org/g"
        return httpx.Response(204)

    client = _client_with_transport(handler)
    result = await client.delete_graph("http://example.org/g")
    assert result is True
    await client.close()


@pytest.mark.asyncio
async def test_delete_graph_not_found_idempotent() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="Graph not found")

    client = _client_with_transport(handler)
    result = await client.delete_graph("http://example.org/g")
    assert result is False
    await client.close()


@pytest.mark.asyncio
async def test_delete_graph_error_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Storage failure")

    client = _client_with_transport(handler)
    with pytest.raises(OxigraphError, match="Failed to delete graph"):
        await client.delete_graph("http://example.org/g")
    await client.close()


@pytest.mark.asyncio
async def test_get_graph_success() -> None:
    data = "<http://example.org/s> <http://example.org/p> <http://example.org/o> ."

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/store"
        assert request.url.params["graph"] == "http://example.org/g"
        assert request.headers["Accept"] == "text/turtle"
        return httpx.Response(200, text=data, headers={"Content-Type": "text/turtle"})

    client = _client_with_transport(handler)
    content = await client.get_graph("http://example.org/g")
    assert content == data
    await client.close()


@pytest.mark.asyncio
async def test_get_graph_not_found() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = _client_with_transport(handler)
    content = await client.get_graph("http://example.org/g")
    assert content is None
    await client.close()


@pytest.mark.asyncio
async def test_query_json_success() -> None:
    json_result = {
        "head": {"vars": ["s", "p", "o"]},
        "results": {
            "bindings": [
                {
                    "s": {"type": "uri", "value": "http://example.org/s"},
                    "p": {"type": "uri", "value": "http://example.org/p"},
                    "o": {"type": "uri", "value": "http://example.org/o"},
                }
            ]
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/query"
        assert request.headers["Content-Type"] == "application/sparql-query"
        assert request.headers["Accept"] == "application/sparql-results+json"
        assert request.content == b"SELECT * WHERE { ?s ?p ?o }"
        return httpx.Response(
            200,
            json=json_result,
            headers={"Content-Type": "application/sparql-results+json"},
        )

    client = _client_with_transport(handler)
    res = await client.query("SELECT * WHERE { ?s ?p ?o }")
    assert res == json_result
    await client.close()


@pytest.mark.asyncio
async def test_query_raw_text_success() -> None:
    ttl = "<http://example.org/s> <http://example.org/p> <http://example.org/o> .\n"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Accept"] == "text/turtle"
        return httpx.Response(200, text=ttl, headers={"Content-Type": "text/turtle"})

    client = _client_with_transport(handler)
    res = await client.query("CONSTRUCT WHERE { ?s ?p ?o }", accept="text/turtle")
    assert res == ttl
    await client.close()


@pytest.mark.asyncio
async def test_query_error_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="Syntax error in SPARQL query")

    client = _client_with_transport(handler)
    with pytest.raises(OxigraphQueryError, match="SPARQL query failed"):
        await client.query("MALFORMED QUERY")
    await client.close()


@pytest.mark.asyncio
async def test_update_success() -> None:
    recorded_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        return httpx.Response(204)

    client = _client_with_transport(handler)
    await client.update("CLEAR ALL")
    assert len(recorded_requests) == 1
    req = recorded_requests[0]
    assert req.method == "POST"
    assert req.url.path == "/update"
    assert req.headers["Content-Type"] == "application/sparql-update"
    assert req.content == b"CLEAR ALL"
    await client.close()


@pytest.mark.asyncio
async def test_update_error_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="Syntax error in update")

    client = _client_with_transport(handler)
    with pytest.raises(OxigraphQueryError, match="SPARQL update failed"):
        await client.update("INVALID UPDATE")
    await client.close()


@pytest.mark.asyncio
async def test_count_triples() -> None:
    sparql_resp = {
        "head": {"vars": ["count"]},
        "results": {
            "bindings": [
                {"count": {"type": "literal", "datatype": "http://www.w3.org/2001/XMLSchema#integer", "value": "42"}}
            ]
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=sparql_resp, headers={"Content-Type": "application/sparql-results+json"})

    client = _client_with_transport(handler)
    count = await client.count_triples()
    assert count == 42
    await client.close()


@pytest.mark.asyncio
async def test_count_triples_fallback_on_parse_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": {"bindings": []}}, headers={"Content-Type": "application/sparql-results+json"})

    client = _client_with_transport(handler)
    count = await client.count_triples()
    assert count == 0
    await client.close()


@pytest.mark.asyncio
async def test_clear_all() -> None:
    recorded: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        return httpx.Response(204)

    client = _client_with_transport(handler)
    await client.clear_all()
    assert len(recorded) == 1
    assert recorded[0].content == b"CLEAR ALL"
    await client.close()


@pytest.mark.asyncio
async def test_connection_error_mapping() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("Connection timed out")

    client = _client_with_transport(handler)
    with pytest.raises(OxigraphConnectionError, match="Could not connect to Oxigraph"):
        await client.put_graph("http://example.org/g", "data")
    await client.close()


@pytest.mark.asyncio
async def test_context_manager() -> None:
    client = OxigraphClient()
    async with client as c:
        assert c is client
    # Client should be closed on exit
    assert client._client is None
