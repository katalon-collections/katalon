import pytest
from httpx import ASGITransport, AsyncClient

from katalon.main import app


@pytest.mark.asyncio
async def test_create_relation_requires_auth() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/v1/relations", json={
            "from_type": "object",
            "from_id": "00000000-0000-0000-0000-000000000001",
            "to_type": "entity",
            "to_id": "00000000-0000-0000-0000-000000000002",
            "relation_type": "depicts",
            "metadata_": {},
        })
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_delete_relation_requires_auth() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.delete("/v1/relations/00000000-0000-0000-0000-000000000001")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_create_relation_invalid_uuid() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/v1/relations",
            json={"from_type": "object", "from_id": "not-a-uuid",
                  "to_type": "entity", "to_id": "also-not-a-uuid",
                  "relation_type": "depicts"},
            headers={"Authorization": "Bearer invalid-token"},
        )
    assert r.status_code in (401, 422)
