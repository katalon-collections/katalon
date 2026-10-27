# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from katalon.core.dependencies import get_db
from katalon.main import app
from katalon.services.seo_service import build_seo_html


def _html(**overrides: object) -> str:
    args: dict = {
        "record_type": "object",
        "record_id": "abc",
        "idno": "OBJ-1",
        "subtype": None,
        "metadata": {
            "title": [{"value": 'Straße "Marrakesch"', "lang": "de"}],
            "description": "**Fett** und [Link](http://x) " + "wort " * 80,
        },
        "site_name": "Museum",
        "base_url": "https://example.org",
        "image_url": "https://example.org/iiif/3/a/full/,600/0/default.jpg",
    }
    return build_seo_html(**{**args, **overrides})


def test_seo_html_tags() -> None:
    out = _html()
    assert '<link rel="canonical" href="https://example.org/objects/abc">' in out
    assert 'property="og:site_name" content="Museum"' in out
    assert 'content="Straße &quot;Marrakesch&quot; | Museum"' in out
    assert 'name="twitter:card" content="summary_large_image"' in out
    assert '"@type": "CreativeWork"' in out
    assert "**" not in out and "](" not in out
    assert "…" in out  # description truncated


def test_seo_html_without_base_url_or_image() -> None:
    out = _html(base_url="", image_url="", metadata={})
    assert "canonical" not in out and "og:url" not in out and "og:image" not in out
    assert 'name="twitter:card" content="summary"' in out
    assert "<title>OBJ-1 | Museum</title>" in out


def test_seo_html_schema_types_and_script_escaping() -> None:
    assert '"@type": "Organization"' in _html(record_type="entity", subtype="institution")
    assert '"@type": "Person"' in _html(record_type="entity")
    assert '"@type": "Place"' in _html(record_type="place")
    assert '"@type": "Collection"' in _html(record_type="collection")
    assert '"@type": "Event"' in _html(record_type="occurrence")
    assert "</script><b>" not in _html(metadata={"title": "</script><b>"})


@pytest.mark.asyncio
async def test_seo_page_not_public_is_404() -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/portal/v1/seo/objects/{uuid.uuid4()}")
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_sitemap_lists_public_records() -> None:
    from datetime import datetime

    rid = uuid.uuid4()
    session = AsyncMock()
    count = MagicMock()
    count.scalar_one.return_value = 1
    session.execute.side_effect = [count, [("object", rid, datetime(2026, 1, 2))]]

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/sitemap.xml")
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 200
    assert f"/objects/{rid}</loc><lastmod>2026-01-02</lastmod>" in response.text
