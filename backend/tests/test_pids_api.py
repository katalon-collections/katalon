import pytest
from httpx import ASGITransport, AsyncClient

from katalon.api.v1 import dnb_urn_mock
from katalon.main import app

# The mock URN registrar is only mounted when settings.debug is True (it must
# never be exposed in production). Ensure it is available for these tests.
if not any(getattr(r, "path", "").startswith("/v1/dnb-urn-mock") for r in app.routes):
    app.include_router(dnb_urn_mock.router, prefix="/v1")


@pytest.mark.asyncio
async def test_register_dnb_urn_requires_auth() -> None:
    payload = {
        "record_type": "object",
        "record_id": "00000000-0000-0000-0000-000000000001",
        "field_name": "urn",
        "target_url": "https://example.org/record/object/1",
        "label": "URN",
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/v1/pids/urn/register", json=payload)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_dnb_mock_suggestion_and_register() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        suggestion = await client.get(
            "/v1/dnb-urn-mock/namespaces/name/urn:nbn:de:test/urn-suggestion"
        )
        assert suggestion.status_code == 200
        urn = suggestion.json()["suggestedUrn"]

        created = await client.post(
            "/v1/dnb-urn-mock/urns",
            json={"urn": urn, "urls": [{"url": "https://example.org/record/1", "priority": 10}]},
        )
        assert created.status_code == 201
        assert created.json()["urn"] == urn
