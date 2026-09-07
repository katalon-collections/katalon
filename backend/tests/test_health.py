# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import pytest
from httpx import ASGITransport, AsyncClient

from katalon.main import app


@pytest.mark.asyncio
async def test_health() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/health")
    assert r.status_code in (200, 503)
    body = r.json()
    assert set(body["checks"]) == {"database", "elasticsearch"}
    # status/code are consistent with the individual checks
    healthy = all(v == "ok" for v in body["checks"].values())
    assert body["status"] == ("ok" if healthy else "degraded")
    assert r.status_code == (200 if healthy else 503)


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
