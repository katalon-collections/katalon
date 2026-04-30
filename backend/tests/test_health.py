import pytest
from httpx import ASGITransport, AsyncClient

from katalon.main import app


@pytest.mark.asyncio
async def test_health() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_openapi_schema() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    assert schema["info"]["title"] == "Katalon API"
