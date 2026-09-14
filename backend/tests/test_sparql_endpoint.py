# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from katalon.api.v1.sparql import validate_read_only_sparql
from katalon.config import settings
from katalon.core.dependencies import get_current_user, try_get_current_user
from katalon.core.models import User
from katalon.integrations.oxigraph import OxigraphConnectionError, OxigraphQueryError
from katalon.main import app


@pytest.fixture
def mock_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="curator@example.org",
        role="editor",
        is_active=True,
    )


@pytest.fixture
def admin_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="admin@example.org",
        role="admin",
        is_active=True,
    )


# --- Unit Tests for validate_read_only_sparql ---


def test_validate_read_only_sparql_valid() -> None:
    valid_queries = [
        "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10",
        "SELECT * WHERE { ?s ?p ?o }",
        "PREFIX foaf: <http://xmlns.com/foaf/0.1/> SELECT ?name WHERE { ?x foaf:name ?name }",
        "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o }",
        "DESCRIBE <http://example.org/item/1>",
        "ASK { ?s ?p ?o }",
        # Subquery
        "SELECT ?s WHERE { { SELECT ?s WHERE { ?s ?p ?o } LIMIT 5 } }",
        # Literal containing update words
        'SELECT ?s WHERE { ?s ?p ?o . FILTER regex(?o, "DELETE FROM table") }',
        'SELECT ?s WHERE { ?s ?p ?o . FILTER(?o = "INSERT DATA") }',
    ]
    for q in valid_queries:
        validate_read_only_sparql(q)  # Should not raise


def test_validate_read_only_sparql_empty() -> None:
    with pytest.raises(Exception) as exc_info:
        validate_read_only_sparql("")
    assert exc_info.value.status_code == 400


def test_validate_read_only_sparql_too_large() -> None:
    large_query = "SELECT * WHERE { ?s ?p ?o } #" + "x" * 70000
    with pytest.raises(Exception) as exc_info:
        validate_read_only_sparql(large_query)
    assert exc_info.value.status_code == 413


def test_validate_read_only_sparql_rejects_updates() -> None:
    forbidden_updates = [
        "INSERT DATA { <http://s> <http://p> <http://o> }",
        "DELETE DATA { <http://s> <http://p> <http://o> }",
        "DELETE WHERE { ?s ?p ?o }",
        "CLEAR ALL",
        "CLEAR GRAPH <http://example.org/g>",
        "DROP ALL",
        "LOAD <http://example.org/remote.rdf>",
        "CREATE GRAPH <http://example.org/new>",
        "ADD <http://example.org/g1> TO <http://example.org/g2>",
        "MOVE <http://example.org/g1> TO <http://example.org/g2>",
        "COPY <http://example.org/g1> TO <http://example.org/g2>",
        # Chained update attempt
        "SELECT * WHERE { ?s ?p ?o } ; DROP ALL",
    ]
    for upd in forbidden_updates:
        with pytest.raises(Exception) as exc_info:
            validate_read_only_sparql(upd)
        assert exc_info.value.status_code == 400


# --- Endpoint Integration Tests via AsyncClient ---


@pytest.mark.asyncio
async def test_sparql_disabled_returns_503() -> None:
    with patch.object(settings, "oxigraph_enabled", False):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/v1/sparql", params={"query": "SELECT * WHERE { ?s ?p ?o }"})
            assert resp.status_code == 503
            assert "disabled" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_sparql_requires_auth_when_configured() -> None:
    with (
        patch.object(settings, "oxigraph_enabled", True),
        patch.object(settings, "sparql_endpoint_enabled", True),
        patch.object(settings, "sparql_require_auth", True),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/v1/sparql", params={"query": "SELECT * WHERE { ?s ?p ?o }"})
            assert resp.status_code == 401


@pytest.mark.asyncio
async def test_sparql_allows_anonymous_when_sparql_require_auth_false() -> None:
    fake_payload = b'{"head":{"vars":[]},"results":{"bindings":[]}}'
    mock_oxigraph = AsyncMock()
    mock_oxigraph.query_raw.return_value = (fake_payload, "application/sparql-results+json")

    with (
        patch.object(settings, "oxigraph_enabled", True),
        patch.object(settings, "sparql_endpoint_enabled", True),
        patch.object(settings, "sparql_require_auth", False),
        patch("katalon.api.v1.sparql.get_oxigraph_client", return_value=mock_oxigraph),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/v1/sparql", params={"query": "SELECT * WHERE { ?s ?p ?o }"})
            assert resp.status_code == 200
            assert resp.content == fake_payload


@pytest.mark.asyncio
async def test_sparql_get_authorized(mock_user: User) -> None:
    app.dependency_overrides[try_get_current_user] = lambda: mock_user
    fake_payload = b'{"head":{"vars":["s"]},"results":{"bindings":[]}}'
    mock_oxigraph = AsyncMock()
    mock_oxigraph.query_raw.return_value = (fake_payload, "application/sparql-results+json")

    try:
        with (
            patch.object(settings, "oxigraph_enabled", True),
            patch.object(settings, "sparql_endpoint_enabled", True),
            patch.object(settings, "sparql_require_auth", True),
            patch("katalon.api.v1.sparql.get_oxigraph_client", return_value=mock_oxigraph),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                query = "SELECT ?s WHERE { ?s ?p ?o } LIMIT 5"
                resp = await client.get(
                    "/v1/sparql",
                    params={"query": query, "default-graph-uri": "urn:katalon:default"},
                    headers={"Accept": "application/sparql-results+json"},
                )
                assert resp.status_code == 200
                assert resp.content == fake_payload
                mock_oxigraph.query_raw.assert_called_once_with(
                    sparql=query,
                    accept="application/sparql-results+json",
                    request_timeout=settings.sparql_query_timeout,
                    default_graph_uris=["urn:katalon:default"],
                    named_graph_uris=None,
                )
    finally:
        app.dependency_overrides.pop(try_get_current_user, None)


@pytest.mark.asyncio
async def test_sparql_post_urlencoded(mock_user: User) -> None:
    app.dependency_overrides[try_get_current_user] = lambda: mock_user
    fake_payload = b'{"head":{"vars":["s"]},"results":{"bindings":[]}}'
    mock_oxigraph = AsyncMock()
    mock_oxigraph.query_raw.return_value = (fake_payload, "application/sparql-results+json")

    try:
        with (
            patch.object(settings, "oxigraph_enabled", True),
            patch.object(settings, "sparql_endpoint_enabled", True),
            patch.object(settings, "sparql_require_auth", True),
            patch("katalon.api.v1.sparql.get_oxigraph_client", return_value=mock_oxigraph),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                query = "SELECT ?s WHERE { ?s ?p ?o } LIMIT 10"
                resp = await client.post(
                    "/v1/sparql",
                    data={"query": query},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                assert resp.status_code == 200
                assert resp.content == fake_payload
    finally:
        app.dependency_overrides.pop(try_get_current_user, None)


@pytest.mark.asyncio
async def test_sparql_post_raw_sparql_query(mock_user: User) -> None:
    app.dependency_overrides[try_get_current_user] = lambda: mock_user
    fake_payload = b"<rdf:RDF></rdf:RDF>"
    mock_oxigraph = AsyncMock()
    mock_oxigraph.query_raw.return_value = (fake_payload, "application/rdf+xml")

    try:
        with (
            patch.object(settings, "oxigraph_enabled", True),
            patch.object(settings, "sparql_endpoint_enabled", True),
            patch.object(settings, "sparql_require_auth", True),
            patch("katalon.api.v1.sparql.get_oxigraph_client", return_value=mock_oxigraph),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                query = "CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o } LIMIT 10"
                resp = await client.post(
                    "/v1/sparql",
                    content=query.encode("utf-8"),
                    headers={
                        "Content-Type": "application/sparql-query",
                        "Accept": "application/rdf+xml",
                    },
                )
                assert resp.status_code == 200
                assert resp.content == fake_payload
                assert resp.headers["content-type"].startswith("application/rdf+xml")
    finally:
        app.dependency_overrides.pop(try_get_current_user, None)


@pytest.mark.asyncio
async def test_sparql_post_unsupported_content_type(mock_user: User) -> None:
    app.dependency_overrides[try_get_current_user] = lambda: mock_user
    try:
        with (
            patch.object(settings, "oxigraph_enabled", True),
            patch.object(settings, "sparql_endpoint_enabled", True),
            patch.object(settings, "sparql_require_auth", True),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/v1/sparql",
                    content=b'{"query": "SELECT *"}',
                    headers={"Content-Type": "application/json"},
                )
                assert resp.status_code == 415
    finally:
        app.dependency_overrides.pop(try_get_current_user, None)


@pytest.mark.asyncio
async def test_sparql_post_update_operation_rejected(mock_user: User) -> None:
    app.dependency_overrides[try_get_current_user] = lambda: mock_user
    try:
        with (
            patch.object(settings, "oxigraph_enabled", True),
            patch.object(settings, "sparql_endpoint_enabled", True),
            patch.object(settings, "sparql_require_auth", True),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/v1/sparql",
                    content=b"DELETE DATA { <http://a> <http://b> <http://c> }",
                    headers={"Content-Type": "application/sparql-query"},
                )
                assert resp.status_code == 400
                assert "Invalid or unauthorized SPARQL query" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(try_get_current_user, None)


@pytest.mark.asyncio
async def test_sparql_timeout_handling(mock_user: User) -> None:
    app.dependency_overrides[try_get_current_user] = lambda: mock_user
    mock_oxigraph = AsyncMock()
    mock_oxigraph.query_raw.side_effect = OxigraphQueryError("SPARQL query timed out after 30.0s")

    try:
        with (
            patch.object(settings, "oxigraph_enabled", True),
            patch.object(settings, "sparql_endpoint_enabled", True),
            patch.object(settings, "sparql_require_auth", True),
            patch("katalon.api.v1.sparql.get_oxigraph_client", return_value=mock_oxigraph),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/v1/sparql", params={"query": "SELECT * WHERE { ?s ?p ?o }"})
                assert resp.status_code == 504
                assert "timed out" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(try_get_current_user, None)


@pytest.mark.asyncio
async def test_sparql_oxigraph_connection_error(mock_user: User) -> None:
    app.dependency_overrides[try_get_current_user] = lambda: mock_user
    mock_oxigraph = AsyncMock()
    mock_oxigraph.query_raw.side_effect = OxigraphConnectionError("Connection refused")

    try:
        with (
            patch.object(settings, "oxigraph_enabled", True),
            patch.object(settings, "sparql_endpoint_enabled", True),
            patch.object(settings, "sparql_require_auth", True),
            patch("katalon.api.v1.sparql.get_oxigraph_client", return_value=mock_oxigraph),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/v1/sparql", params={"query": "SELECT * WHERE { ?s ?p ?o }"})
                assert resp.status_code == 502
                assert "Could not reach RDF triple store" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(try_get_current_user, None)


@pytest.mark.asyncio
async def test_sparql_root_endpoint_and_v1_alias(mock_user: User) -> None:
    app.dependency_overrides[try_get_current_user] = lambda: mock_user
    fake_payload = b'{"head":{"vars":["x"]},"results":{"bindings":[]}}'
    mock_oxigraph = AsyncMock()
    mock_oxigraph.query_raw.return_value = (fake_payload, "application/sparql-results+json")

    try:
        with (
            patch.object(settings, "oxigraph_enabled", True),
            patch.object(settings, "sparql_endpoint_enabled", True),
            patch.object(settings, "sparql_require_auth", True),
            patch("katalon.api.v1.sparql.get_oxigraph_client", return_value=mock_oxigraph),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                # Root /sparql
                resp_root = await client.get("/sparql", params={"query": "SELECT ?x WHERE { ?x ?p ?o }"})
                assert resp_root.status_code == 200
                assert resp_root.content == fake_payload

                # Alias /v1/sparql
                resp_alias = await client.get("/v1/sparql", params={"query": "SELECT ?x WHERE { ?x ?p ?o }"})
                assert resp_alias.status_code == 200
                assert resp_alias.content == fake_payload
    finally:
        app.dependency_overrides.pop(try_get_current_user, None)


@pytest.mark.asyncio
async def test_sparql_status_disabled(admin_user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: admin_user
    try:
        with patch.object(settings, "oxigraph_enabled", False):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/sparql/status")
                assert resp.status_code == 200
                data = resp.json()
                assert data["enabled"] is False
                assert data["reachable"] is False
                assert data["triples_count"] is None
                assert data["endpoint_url"] == "/sparql"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_sparql_status_enabled_and_reachable(admin_user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: admin_user
    mock_oxigraph = AsyncMock()
    mock_oxigraph.health.return_value = True
    mock_oxigraph.count_triples.return_value = 14205

    try:
        with (
            patch.object(settings, "oxigraph_enabled", True),
            patch("katalon.api.v1.sparql.get_oxigraph_client", return_value=mock_oxigraph),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/sparql/status")
                assert resp.status_code == 200
                data = resp.json()
                assert data["enabled"] is True
                assert data["reachable"] is True
                assert data["triples_count"] == 14205

                # Also test /v1/sparql/status alias
                resp_alias = await client.get("/v1/sparql/status")
                assert resp_alias.status_code == 200
                assert resp_alias.json()["triples_count"] == 14205
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_sparql_status_permission_check(mock_user: User) -> None:
    # Unauthenticated -> 401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/sparql/status")
        assert resp.status_code == 401

    # Editor role -> 403
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/sparql/status")
            assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_sparql_rebuild_disabled(admin_user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: admin_user
    try:
        with patch.object(settings, "oxigraph_enabled", False):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/sparql/rebuild")
                assert resp.status_code == 503
                assert "disabled" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_sparql_rebuild_enqueues_task(admin_user: User) -> None:
    app.dependency_overrides[get_current_user] = lambda: admin_user
    try:
        with (
            patch.object(settings, "oxigraph_enabled", True),
            patch("katalon.workers.enqueue.enqueue_or_503") as mock_enqueue,
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/sparql/rebuild")
                assert resp.status_code == 200
                assert resp.json() == {"status": "queued"}
                mock_enqueue.assert_called_once()

                # Alias /v1/sparql/rebuild
                resp_alias = await client.post("/v1/sparql/rebuild")
                assert resp_alias.status_code == 200
                assert resp_alias.json() == {"status": "queued"}
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_sparql_rebuild_permission_check(mock_user: User) -> None:
    # Unauthenticated -> 401
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/sparql/rebuild")
        assert resp.status_code == 401

    # Editor role -> 403
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/sparql/rebuild")
            assert resp.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_saved_sparql_queries_crud(admin_user: User) -> None:
    from unittest.mock import MagicMock

    from katalon.core.dependencies import get_current_user, get_db
    from katalon.core.models import SavedSparqlQuery

    storage: dict[uuid.UUID, SavedSparqlQuery] = {}

    class MockSession:
        def add(self, item: SavedSparqlQuery) -> None:
            storage[item.id] = item

        async def commit(self) -> None:
            pass

        async def refresh(self, item: SavedSparqlQuery) -> None:
            pass

        async def delete(self, item: SavedSparqlQuery) -> None:
            storage.pop(item.id, None)

        async def execute(self, stmt: Any) -> Any:
            mock_res = MagicMock()
            params = getattr(stmt.compile(), "params", {})
            target_id = None
            for val in params.values():
                if isinstance(val, (uuid.UUID, str)):
                    try:
                        target_id = uuid.UUID(str(val))
                        break
                    except ValueError:
                        pass
            if target_id is not None:
                mock_res.scalar_one_or_none.return_value = storage.get(target_id)
            else:
                mock_res.scalars.return_value.all.return_value = list(storage.values())
            return mock_res

    mock_session = MockSession()

    async def override_db():
        yield mock_session

    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[get_db] = override_db
    try:
        with patch.object(settings, "oxigraph_enabled", True):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                # 1. Create
                create_payload = {
                    "title": "Test Query All Objects",
                    "description": "Test query description",
                    "query": "SELECT ?s ?title WHERE { ?s crm:P102_has_title ?title } LIMIT 10",
                    "tags": ["test", "objects"],
                    "is_shared": True,
                }
                resp = await client.post("/v1/sparql/queries", json=create_payload)
                assert resp.status_code == 201, resp.text
                created_data = resp.json()
                query_id = created_data["id"]
                assert created_data["title"] == "Test Query All Objects"
                assert created_data["tags"] == ["test", "objects"]

                # 2. Reject non-read-only in create
                bad_payload = {
                    "title": "Bad Query",
                    "query": "INSERT DATA { <http://s> <http://p> <http://o> }",
                }
                resp_bad = await client.post("/v1/sparql/queries", json=bad_payload)
                assert resp_bad.status_code == 400

                # 3. Get single
                resp_get = await client.get(f"/v1/sparql/queries/{query_id}")
                assert resp_get.status_code == 200
                assert resp_get.json()["id"] == query_id

                # 4. List and filter
                resp_list = await client.get("/v1/sparql/queries", params={"tag": "objects"})
                assert resp_list.status_code == 200
                assert any(q["id"] == query_id for q in resp_list.json())

                resp_search = await client.get("/v1/sparql/queries", params={"q": "All Objects"})
                assert resp_search.status_code == 200
                assert any(q["id"] == query_id for q in resp_search.json())

                # 5. Update
                resp_update = await client.put(
                    f"/v1/sparql/queries/{query_id}",
                    json={"title": "Updated Query Title", "tags": ["updated"]},
                )
                assert resp_update.status_code == 200
                assert resp_update.json()["title"] == "Updated Query Title"
                assert resp_update.json()["tags"] == ["updated"]

                # 6. Delete
                resp_del = await client.delete(f"/v1/sparql/queries/{query_id}")
                assert resp_del.status_code == 204

                resp_get_after = await client.get(f"/v1/sparql/queries/{query_id}")
                assert resp_get_after.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_saved_sparql_queries_disabled_when_oxigraph_false(admin_user: User) -> None:
    from katalon.core.dependencies import get_current_user

    app.dependency_overrides[get_current_user] = lambda: admin_user
    try:
        with patch.object(settings, "oxigraph_enabled", False):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/v1/sparql/queries")
                assert resp.status_code == 503
                assert "disabled" in resp.json()["detail"]

                resp_nl = await client.post("/v1/sparql/nl2sparql", json={"prompt": "Zeige Objekte"})
                assert resp_nl.status_code == 503
                assert "disabled" in resp_nl.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_nl2sparql_endpoint_success(admin_user: User) -> None:
    from katalon.core.dependencies import get_current_user

    app.dependency_overrides[get_current_user] = lambda: admin_user
    fake_result = {
        "sparql": "SELECT * WHERE { ?s ?p ?o } LIMIT 50",
        "explanation": "Generierte Abfrage für alle Triples.",
    }
    try:
        with (
            patch.object(settings, "oxigraph_enabled", True),
            patch(
                "katalon.services.sparql_ai_service.generate_sparql_from_prompt",
                new_callable=AsyncMock,
                return_value=fake_result,
            ),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/v1/sparql/nl2sparql", json={"prompt": "Zeige alle Triples"})
                assert resp.status_code == 200
                assert resp.json()["sparql"] == fake_result["sparql"]
                assert resp.json()["explanation"] == fake_result["explanation"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)
