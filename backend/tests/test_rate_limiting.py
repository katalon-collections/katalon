# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from katalon.config import settings
from katalon.core.dependencies import get_db
from katalon.core.limiter import limiter
from katalon.main import app


@pytest.mark.asyncio
async def test_search_rate_limit_allows_under_limit() -> None:
    """Requests under the rate limit should succeed."""
    result = {"total": 0, "page": 1, "page_size": 20, "items": [], "facets": {}}
    config_result = MagicMock()
    config_result.scalar_one_or_none.return_value = None
    session = AsyncMock()
    session.execute.return_value = config_result

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        with patch("katalon.api.v1.search.search_service.search", AsyncMock(return_value=result)):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                # First few requests should succeed
                for _ in range(3):
                    r = await client.get("/portal/v1/search?q=test")
                    assert r.status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_oai_rate_limit_allows_under_limit() -> None:
    """OAI-PMH requests under the rate limit should succeed."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for _ in range(3):
                r = await client.get("/oai?verb=Identify")
                assert r.status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_oai_is_available_without_api_version_prefix() -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/oai?verb=Identify")
            assert r.status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_oai_is_not_versioned_rest_endpoint() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/v1/oai?verb=Identify")
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_authorities_search_rate_limit_allows_under_limit() -> None:
    """Authority search requests under the rate limit should succeed."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(3):
            r = await client.get("/v1/authorities/search?source=gnd&q=test")
            assert r.status_code in (200, 401)  # 401 if auth required, but limiter still applies


@pytest.mark.asyncio
async def test_rate_limit_is_per_client_ip_behind_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two clients behind the same proxy must get independent buckets.

    Regression for the deployment bug where uvicorn ran without a trusted
    proxy: every request carried the nginx container IP, so one crawler
    exhausted the shared bucket and locked out all other visitors.
    """
    monkeypatch.setattr(settings, "rate_limit_public_search", "2/minute")
    limiter.reset()

    result = {"total": 0, "page": 1, "page_size": 20, "items": [], "facets": {}}
    config_result = MagicMock()
    config_result.scalar_one_or_none.return_value = None
    session = AsyncMock()
    session.execute.return_value = config_result

    async def override_db():
        yield session

    # Mirrors `uvicorn --proxy-headers` with FORWARDED_ALLOW_IPS="*".
    proxied = ProxyHeadersMiddleware(app, trusted_hosts="*")

    app.dependency_overrides[get_db] = override_db
    try:
        with patch("katalon.api.v1.search.search_service.search", AsyncMock(return_value=result)):
            async with AsyncClient(
                transport=ASGITransport(app=proxied), base_url="http://test"
            ) as client:
                bot = {"X-Forwarded-For": "203.0.113.7"}
                for _ in range(2):
                    assert (await client.get("/portal/v1/search?q=t", headers=bot)).status_code == 200
                # Same client exceeds its own limit.
                assert (await client.get("/portal/v1/search?q=t", headers=bot)).status_code == 429
                # A different client is unaffected by the bot's traffic.
                visitor = {"X-Forwarded-For": "198.51.100.4"}
                assert (
                    await client.get("/portal/v1/search?q=t", headers=visitor)
                ).status_code == 200
    finally:
        app.dependency_overrides.pop(get_db, None)
        limiter.reset()
