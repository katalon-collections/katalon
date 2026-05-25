import pytest
from httpx import ASGITransport, AsyncClient

from katalon.main import app


@pytest.mark.asyncio
async def test_search_rate_limit_allows_under_limit() -> None:
    """Requests under the rate limit should succeed."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # First few requests should succeed
        for _ in range(3):
            r = await client.get("/v1/search?q=test")
            assert r.status_code == 200


@pytest.mark.asyncio
async def test_oai_rate_limit_allows_under_limit() -> None:
    """OAI-PMH requests under the rate limit should succeed."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(3):
            r = await client.get("/v1/oai?verb=Identify")
            assert r.status_code == 200


@pytest.mark.asyncio
async def test_authorities_search_rate_limit_allows_under_limit() -> None:
    """Authority search requests under the rate limit should succeed."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(3):
            r = await client.get("/v1/authorities/search?source=gnd&q=test")
            assert r.status_code in (200, 401)  # 401 if auth required, but limiter still applies
