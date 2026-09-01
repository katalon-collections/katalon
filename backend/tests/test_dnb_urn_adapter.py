# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

from unittest.mock import patch

import pytest

from katalon.integrations.dnb_urn_adapter import DnbUrnAdapter


class _Response:
    def __init__(self, data: dict, status: int = 200) -> None:
        self.status_code = status
        self._data = data

    def json(self) -> dict:
        return self._data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


def _http(get_data: dict | None = None, post_data: dict | None = None):
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def get(self, *args, **kwargs) -> _Response:
            return _Response(get_data or {})

        async def post(self, *args, **kwargs) -> _Response:
            return _Response(post_data or {})

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            pass

    return FakeAsyncClient


@pytest.mark.asyncio
async def test_suggest_urn_parses_api_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "katalon.integrations.dnb_urn_adapter.settings.dnb_urn_enabled", True
    )
    monkeypatch.setattr(
        "katalon.integrations.dnb_urn_adapter.settings.dnb_urn_api_url", "http://example.org"
    )
    monkeypatch.setattr(
        "katalon.integrations.dnb_urn_adapter.settings.dnb_urn_namespace", "urn:nbn:de:test"
    )
    monkeypatch.setattr(
        "katalon.integrations.dnb_urn_adapter.settings.dnb_urn_username", "user"
    )
    monkeypatch.setattr(
        "katalon.integrations.dnb_urn_adapter.settings.dnb_urn_password", "pass"
    )
    with patch(
        "katalon.integrations.dnb_urn_adapter.httpx.AsyncClient",
        _http(get_data={"suggestedUrn": "urn:nbn:de:test-123"}),
    ):
        urn = await DnbUrnAdapter().suggest_urn()
    assert urn == "urn:nbn:de:test-123"


@pytest.mark.asyncio
async def test_register_urn_parses_registered_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "katalon.integrations.dnb_urn_adapter.settings.dnb_urn_enabled", True
    )
    monkeypatch.setattr(
        "katalon.integrations.dnb_urn_adapter.settings.dnb_urn_api_url", "http://example.org"
    )
    monkeypatch.setattr(
        "katalon.integrations.dnb_urn_adapter.settings.dnb_urn_namespace", "urn:nbn:de:test"
    )
    monkeypatch.setattr(
        "katalon.integrations.dnb_urn_adapter.settings.dnb_urn_username", "user"
    )
    monkeypatch.setattr(
        "katalon.integrations.dnb_urn_adapter.settings.dnb_urn_password", "pass"
    )
    with patch(
        "katalon.integrations.dnb_urn_adapter.httpx.AsyncClient",
        _http(post_data={"urn": "urn:nbn:de:test-123"}),
    ):
        urn = await DnbUrnAdapter().register_urn(
            "urn:nbn:de:test-123", "https://example.org/record/1"
        )
    assert urn == "urn:nbn:de:test-123"
