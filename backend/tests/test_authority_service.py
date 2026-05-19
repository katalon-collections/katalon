from unittest.mock import AsyncMock

import pytest

from katalon.integrations.authority import AuthorityHit
from katalon.services import authority_service


def _hit(**kwargs) -> AuthorityHit:
    defaults = {"source": "mock", "external_id": "1", "label": "Test"}
    return AuthorityHit(**{**defaults, **kwargs})


@pytest.fixture(autouse=True)
def reset_cache():
    """Ensure the authority_service cache is clean before and after each test."""
    authority_service.invalidate_cache()
    yield
    authority_service.invalidate_cache()


# ── list_sources ─────────────────────────────────────────────────────────────


def test_list_sources_returns_all_builtins() -> None:
    sources = authority_service.list_sources()
    assert set(sources) == {"gnd", "geonames", "viaf", "wikidata", "tgn", "iconclass"}


def test_list_sources_returns_six_entries() -> None:
    assert len(authority_service.list_sources()) == 6


# ── search ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_unknown_source_returns_none() -> None:
    authority_service._cache = {"gnd": authority_service._BUILTIN["gnd"]}
    result = await authority_service.search("nonexistent_source", "test")
    assert result is None


@pytest.mark.asyncio
async def test_search_delegates_to_adapter() -> None:
    expected = [_hit(external_id="42", label="Treffer")]
    mock_adapter = AsyncMock()
    mock_adapter.search = AsyncMock(return_value=expected)
    authority_service._cache = {"mock": mock_adapter}

    result = await authority_service.search("mock", "suchbegriff", limit=5)

    mock_adapter.search.assert_awaited_once_with("suchbegriff", 5)
    assert result == expected


@pytest.mark.asyncio
async def test_search_default_limit_is_ten() -> None:
    mock_adapter = AsyncMock()
    mock_adapter.search = AsyncMock(return_value=[])
    authority_service._cache = {"mock": mock_adapter}

    await authority_service.search("mock", "test")

    mock_adapter.search.assert_awaited_once_with("test", 10)


# ── fetch ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_unknown_source_returns_none() -> None:
    authority_service._cache = {"gnd": authority_service._BUILTIN["gnd"]}
    result = await authority_service.fetch("nonexistent_source", "123")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_delegates_to_adapter() -> None:
    expected = _hit(external_id="42", label="Gefundenes Objekt")
    mock_adapter = AsyncMock()
    mock_adapter.fetch = AsyncMock(return_value=expected)
    authority_service._cache = {"mock": mock_adapter}

    result = await authority_service.fetch("mock", "42")

    mock_adapter.fetch.assert_awaited_once_with("42")
    assert result == expected


@pytest.mark.asyncio
async def test_fetch_adapter_returns_none_propagated() -> None:
    mock_adapter = AsyncMock()
    mock_adapter.fetch = AsyncMock(return_value=None)
    authority_service._cache = {"mock": mock_adapter}

    result = await authority_service.fetch("mock", "missing-id")
    assert result is None


# ── cache ─────────────────────────────────────────────────────────────────────


def test_invalidate_cache_resets_to_none() -> None:
    authority_service._cache = {"gnd": authority_service._BUILTIN["gnd"]}
    authority_service.invalidate_cache()
    assert authority_service._cache is None


@pytest.mark.asyncio
async def test_list_enabled_sources_uses_cache() -> None:
    authority_service._cache = {"gnd": authority_service._BUILTIN["gnd"], "viaf": authority_service._BUILTIN["viaf"]}
    enabled = await authority_service.list_enabled_sources()
    assert set(enabled) == {"gnd", "viaf"}
