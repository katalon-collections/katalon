# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import re

import pytest

import katalon.integrations.ark_adapter as ark_module
from katalon.integrations.ark_adapter import ArkAdapter, ArkAdapterError, ark_resolver_link


def test_mint_format_uses_test_naan(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ark_module.settings, "ark_enabled", True)
    monkeypatch.setattr(ark_module.settings, "ark_naan", "99999")
    ark = ArkAdapter().mint()
    assert re.fullmatch(r"ark:/99999/[a-z2-7]{10}", ark)


def test_mint_respects_suffix_length(monkeypatch: pytest.MonkeyPatch) -> None:
    # Patch the settings object the adapter actually reads (module-local
    # reference — katalon.config may be reloaded by integration tests).
    monkeypatch.setattr(ark_module.settings, "ark_suffix_length", 16)
    monkeypatch.setattr(ark_module.settings, "ark_enabled", True)
    monkeypatch.setattr(ark_module.settings, "ark_naan", "99999")
    ark = ArkAdapter().mint()
    assert re.fullmatch(r"ark:/99999/[a-z2-7]{16}", ark)


def test_mint_disabled_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ark_module.settings, "ark_enabled", False)
    with pytest.raises(ArkAdapterError, match="deaktiviert"):
        ArkAdapter().mint()


def test_mint_missing_naan_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ark_module.settings, "ark_enabled", True)
    monkeypatch.setattr(ark_module.settings, "ark_naan", "")
    with pytest.raises(ArkAdapterError, match="ARK_NAAN"):
        ArkAdapter().mint()


def test_resolver_link() -> None:
    assert ark_resolver_link("ark:/99999/abc123") == "https://n2t.net/ark:/99999/abc123"
