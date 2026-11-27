# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient, Response

from katalon.main import _health_caller, app


async def _get_health(headers: dict[str, str] | None = None) -> Response:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get("/health", headers=headers)


@pytest.mark.asyncio
async def test_health_anonymous_sees_only_status() -> None:
    r = await _get_health()
    assert r.status_code in (200, 503)
    assert r.json() == {"status": "ok" if r.status_code == 200 else "degraded"}


@pytest.mark.asyncio
async def test_health_authenticated_sees_details() -> None:
    app.dependency_overrides[_health_caller] = lambda: SimpleNamespace(role="admin")
    try:
        r = await _get_health()
    finally:
        del app.dependency_overrides[_health_caller]
    body = r.json()
    assert set(body["checks"]) == {"database", "elasticsearch", "redis", "cantaloupe", "beat_heartbeat"}
    # informational only, never gate the status code
    assert "queue_backlog" in body
    assert "backup_age_hours" in body
    # status/code are consistent with the individual checks
    healthy = all(v == "ok" for v in body["checks"].values())
    assert body["status"] == ("ok" if healthy else "degraded")
    assert r.status_code == (200 if healthy else 503)


@pytest.mark.asyncio
async def test_health_survives_failing_authentication() -> None:
    with patch("katalon.main.try_get_current_user", AsyncMock(side_effect=OSError("db down"))):
        r = await _get_health({"X-API-Key": "ktn_x"})
    assert r.status_code in (200, 503)
    assert set(r.json()) == {"status"}


@pytest.mark.asyncio
async def test_openapi_schema() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    assert schema["info"]["title"] == "Katalon API"
    operation_ids = [
        operation["operationId"]
        for path in schema["paths"].values()
        for operation in path.values()
        if isinstance(operation, dict) and "operationId" in operation
    ]
    assert len(operation_ids) == len(set(operation_ids))

    refresh = schema["paths"]["/v1/auth/refresh"]["post"]
    assert refresh["security"] == [{"RefreshCookie": []}]
    assert "requestBody" not in refresh
    assert "Set-Cookie" in refresh["responses"]["200"]["headers"]
