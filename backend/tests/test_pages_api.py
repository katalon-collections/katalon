from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from katalon.database import get_db
from katalon.main import app


def _make_session(pages: list | None = None) -> AsyncMock:
    """Async DB session mock. Returns given pages list for .scalars().all()
    and None for .scalar_one_or_none()."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = pages or []
    result.scalar_one_or_none.return_value = None

    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.delete = AsyncMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def empty_db():
    session = _make_session([])

    async def override():
        yield session

    app.dependency_overrides[get_db] = override
    yield session
    app.dependency_overrides.pop(get_db, None)


# ── Public endpoints ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_pages_public_returns_200(empty_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/portal/v1/pages")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_get_page_not_found_returns_404(empty_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/portal/v1/pages/nonexistent-slug")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_page_slug_with_special_chars_404(empty_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/portal/v1/pages/does-not-exist-123")
    assert r.status_code == 404


# ── Auth-required endpoints ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_all_pages_admin_requires_auth() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/v1/pages/admin")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_create_page_requires_auth() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/v1/pages", json={
            "slug": "test-seite",
            "title": {"de": "Testseite"},
            "content": {"de": "Inhalt"},
        })
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_update_page_requires_auth() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.put("/v1/pages/test-seite", json={"is_published": True})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_delete_page_requires_auth() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.delete("/v1/pages/test-seite")
    assert r.status_code == 401


# ── Authority API auth guards ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_authority_sources_requires_auth() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/v1/authorities/")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_authority_search_requires_auth() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/v1/authorities/search", params={"source": "gnd", "q": "beethoven"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_authority_fetch_requires_auth() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/v1/authorities/fetch", params={"source": "gnd", "id": "118508237"})
    assert r.status_code == 401
