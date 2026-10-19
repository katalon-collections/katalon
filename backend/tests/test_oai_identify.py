# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from katalon.config import settings
from katalon.core.dependencies import get_db
from katalon.main import app


async def _identify() -> str:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://internal:8000") as client:
            response = await client.get("/oai?verb=Identify")
        assert response.status_code == 200
        return response.text
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_identify_uses_configured_base_url() -> None:
    with patch.object(settings, "oai_base_url", "https://katalon.example.org/oai"):
        xml = await _identify()
    assert "<baseURL>https://katalon.example.org/oai</baseURL>" in xml
    assert 'verb="Identify">https://katalon.example.org/oai</request>' in xml


@pytest.mark.asyncio
async def test_identify_derives_base_url_from_request_without_setting() -> None:
    with patch.object(settings, "oai_base_url", ""):
        xml = await _identify()
    assert "<baseURL>http://internal:8000/oai</baseURL>" in xml


@pytest.mark.asyncio
async def test_identify_admin_email_falls_back_when_compose_passes_empty_value() -> None:
    with (
        patch.object(settings, "oai_admin_email", ""),
        patch.object(settings, "default_admin_email", "sammlung@example.org"),
    ):
        xml = await _identify()
    assert "<adminEmail>sammlung@example.org</adminEmail>" in xml
