# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from katalon.integrations.authority import AuthorityHit
from katalon.services import authority_service


def _hit(**kwargs) -> AuthorityHit:
    defaults = {"source": "mock", "external_id": "1", "label": "Test"}
    return AuthorityHit(**{**defaults, **kwargs})


# ── list_sources ─────────────────────────────────────────────────────────────


def test_list_sources_returns_all_builtins() -> None:
    sources = authority_service.list_sources()
    assert set(sources) == {
        "gnd", "gnd-person", "gnd-subject", "geonames", "viaf", "wikidata", "tgn", "iconclass", "aat",
    }


def test_list_sources_returns_nine_entries() -> None:
    assert len(authority_service.list_sources()) == 9


def test_gnd_variants_configured_with_source_id_and_filters() -> None:
    p = authority_service._BUILTIN["gnd-person"]()
    s = authority_service._BUILTIN["gnd-subject"]()
    g = authority_service._BUILTIN["gnd"]()
    assert getattr(p, "source_id", None) == "gnd-person"
    assert getattr(p, "filter_type", None) == "type:Person"
    assert getattr(s, "source_id", None) == "gnd-subject"
    assert getattr(s, "filter_type", None) == "type:SubjectHeading"
    assert getattr(g, "source_id", None) == "gnd"
    assert getattr(g, "filter_type", None) is None


# ── search ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_unknown_source_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authority_service, "_load_registry", AsyncMock(return_value={}))
    result = await authority_service.search("nonexistent_source", "test")
    assert result is None


@pytest.mark.asyncio
async def test_search_delegates_to_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = [_hit(external_id="42", label="Treffer")]
    mock_adapter = AsyncMock()
    mock_adapter.search = AsyncMock(return_value=expected)
    monkeypatch.setattr(authority_service, "_load_registry", AsyncMock(return_value={"mock": mock_adapter}))

    result = await authority_service.search("mock", "suchbegriff", limit=5)

    mock_adapter.search.assert_awaited_once_with("suchbegriff", 5)
    assert result == expected


@pytest.mark.asyncio
async def test_search_default_limit_is_ten(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_adapter = AsyncMock()
    mock_adapter.search = AsyncMock(return_value=[])
    monkeypatch.setattr(authority_service, "_load_registry", AsyncMock(return_value={"mock": mock_adapter}))

    await authority_service.search("mock", "test")

    mock_adapter.search.assert_awaited_once_with("test", 10)


# ── fetch ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_unknown_source_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(authority_service, "_load_registry", AsyncMock(return_value={}))
    result = await authority_service.fetch("nonexistent_source", "123")
    assert result is None


@pytest.mark.asyncio
async def test_fetch_delegates_to_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = _hit(external_id="42", label="Gefundenes Objekt")
    mock_adapter = AsyncMock()
    mock_adapter.fetch = AsyncMock(return_value=expected)
    monkeypatch.setattr(authority_service, "_load_registry", AsyncMock(return_value={"mock": mock_adapter}))

    result = await authority_service.fetch("mock", "42")

    mock_adapter.fetch.assert_awaited_once_with("42")
    assert result == expected


@pytest.mark.asyncio
async def test_fetch_adapter_returns_none_propagated(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_adapter = AsyncMock()
    mock_adapter.fetch = AsyncMock(return_value=None)
    monkeypatch.setattr(authority_service, "_load_registry", AsyncMock(return_value={"mock": mock_adapter}))

    result = await authority_service.fetch("mock", "missing-id")
    assert result is None


# ── default_label / default_adapter_class ──────────────────────────────────────


def test_default_label_known_source() -> None:
    assert authority_service.default_label("gnd") == "GND (Gemeinsame Normdatei)"


def test_default_label_unknown_source_falls_back_to_uppercase() -> None:
    assert authority_service.default_label("myadapter") == "MYADAPTER"


def test_default_adapter_class_known_source() -> None:
    assert authority_service.default_adapter_class("aat") == "katalon.integrations.aat_adapter.AATAdapter"


def test_default_adapter_class_unknown_source_returns_none() -> None:
    assert authority_service.default_adapter_class("nonexistent") is None


# ── _load_registry: DB-disabled sources must not stay reachable ────────────────


@dataclass
class _FakeDBRow:
    id: str
    is_enabled: bool
    config: dict[str, Any] = field(default_factory=dict)


class _FakeScalars:
    def __init__(self, rows: list[_FakeDBRow]) -> None:
        self._rows = rows

    def all(self) -> list[_FakeDBRow]:
        return self._rows


class _FakeResult:
    def __init__(self, rows: list[_FakeDBRow]) -> None:
        self._rows = rows

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._rows)


class _FakeSession:
    def __init__(self, rows: list[_FakeDBRow]) -> None:
        self._rows = rows

    async def execute(self, *args, **kwargs) -> _FakeResult:
        return _FakeResult(self._rows)

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *args) -> None:
        pass


def _fake_session_local(rows: list[_FakeDBRow]):
    def _factory(*_args: Any) -> _FakeSession:
        return _FakeSession(rows)
    return _factory


@pytest.mark.asyncio
async def test_load_registry_excludes_disabled_db_source() -> None:
    rows = [_FakeDBRow(id="gnd", is_enabled=False)]
    with patch("katalon.core.isolated_session.isolated_session", _fake_session_local(rows)):
        registry = await authority_service._load_registry()
    assert "gnd" not in registry
    assert "viaf" in registry


@pytest.mark.asyncio
async def test_load_registry_keeps_enabled_db_source() -> None:
    rows = [_FakeDBRow(id="gnd", is_enabled=True)]
    with patch("katalon.core.isolated_session.isolated_session", _fake_session_local(rows)):
        registry = await authority_service._load_registry()
    assert "gnd" in registry


@pytest.mark.asyncio
async def test_registry_observes_committed_toggle_without_local_invalidation() -> None:
    rows = [_FakeDBRow(id="gnd", is_enabled=True)]
    with patch("katalon.core.isolated_session.isolated_session", _fake_session_local(rows)):
        assert "gnd" in await authority_service.list_enabled_sources()
        rows[0].is_enabled = False
        assert "gnd" not in await authority_service.list_enabled_sources()
        assert await authority_service.search("gnd", "test") is None
        assert await authority_service.fetch("gnd", "123") is None
        rows[0].is_enabled = True
        assert "gnd" in await authority_service.list_enabled_sources()


@pytest.mark.asyncio
async def test_removed_config_restores_defaults_without_mutating_earlier_adapter() -> None:
    rows = [_FakeDBRow(id="gnd-person", is_enabled=True, config={"filter_type": "custom"})]
    with patch("katalon.core.isolated_session.isolated_session", _fake_session_local(rows)):
        configured = (await authority_service._load_registry())["gnd-person"]
        rows[0].config = {}
        restored = (await authority_service._load_registry())["gnd-person"]
    assert getattr(configured, "filter_type") == "custom"
    assert getattr(restored, "filter_type") == "type:Person"
    assert restored.source_id == "gnd-person"
    assert configured is not restored


@pytest.mark.asyncio
async def test_database_failure_does_not_cache_fallback_after_recovery() -> None:
    with patch("katalon.core.isolated_session.isolated_session", side_effect=RuntimeError("offline")):
        assert "gnd" in await authority_service.list_enabled_sources()
    rows = [_FakeDBRow(id="gnd", is_enabled=False)]
    with patch("katalon.core.isolated_session.isolated_session", _fake_session_local(rows)):
        assert "gnd" not in await authority_service.list_enabled_sources()
