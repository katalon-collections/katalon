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
