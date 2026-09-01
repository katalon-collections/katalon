# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import importlib

from katalon.integrations.aat_adapter import AATAdapter
from katalon.integrations.authority import AuthorityHit, AuthoritySource
from katalon.integrations.geonames_adapter import GeonamesAdapter
from katalon.integrations.gnd_adapter import GNDAdapter
from katalon.integrations.iconclass_adapter import ICONCLASSAdapter
from katalon.integrations.tgn_adapter import TGNAdapter
from katalon.integrations.viaf_adapter import VIAFAdapter
from katalon.integrations.wikidata_adapter import WikidataAdapter

# Built-in adapters always available (can be overridden by DB config)
_BUILTIN: dict[str, AuthoritySource] = {
    "gnd":       GNDAdapter(),
    "geonames":  GeonamesAdapter(),
    "viaf":      VIAFAdapter(),
    "wikidata":  WikidataAdapter(),
    "tgn":       TGNAdapter(),
    "iconclass": ICONCLASSAdapter(),
    "aat":       AATAdapter(),
}

_LABELS: dict[str, str] = {
    "gnd":       "GND (Gemeinsame Normdatei)",
    "geonames":  "GeoNames",
    "viaf":      "VIAF",
    "wikidata":  "Wikidata",
    "tgn":       "Getty TGN (Thesaurus of Geographic Names)",
    "iconclass": "Iconclass",
    "aat":       "Getty AAT (Art & Architecture Thesaurus)",
}


def default_label(source_id: str) -> str:
    return _LABELS.get(source_id, source_id.upper())


def default_adapter_class(source_id: str) -> str | None:
    adapter = _BUILTIN.get(source_id)
    if adapter is None:
        return None
    cls = type(adapter)
    return f"{cls.__module__}.{cls.__qualname__}"

# Cache: source_id → adapter (populated lazily from DB)
_cache: dict[str, AuthoritySource] | None = None


async def _load_registry() -> dict[str, AuthoritySource]:
    """Load enabled adapters from authority_sources table, fall back to builtins."""
    global _cache
    if _cache is not None:
        return _cache
    try:
        from sqlalchemy import select

        from katalon.core.models import AuthoritySource as AuthoritySourceModel
        from katalon.database import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(AuthoritySourceModel))
            db_sources = result.scalars().all()

        # Start with all builtins, then apply DB overrides (including disabling)
        registry: dict[str, AuthoritySource] = dict(_BUILTIN)
        for src in db_sources:
            if not src.is_enabled:
                registry.pop(src.id, None)
                continue
            if src.id in _BUILTIN:
                adapter = _BUILTIN[src.id]
                for key, val in (src.config or {}).items():
                    if hasattr(adapter, key):
                        setattr(adapter, key, val)
                registry[src.id] = adapter
            else:
                # Dynamically load custom adapter_class
                try:
                    module_path, cls_name = src.adapter_class.rsplit(".", 1)
                    mod = importlib.import_module(module_path)
                    cls = getattr(mod, cls_name)
                    registry[src.id] = cls(**(src.config or {}))
                except Exception:
                    pass
        _cache = registry
    except Exception:
        _cache = dict(_BUILTIN)
    return _cache


def invalidate_cache() -> None:
    global _cache
    _cache = None


def list_sources() -> list[str]:
    return list(_BUILTIN.keys())


async def list_enabled_sources() -> list[str]:
    registry = await _load_registry()
    return list(registry.keys())


async def search(source_id: str, query: str, limit: int = 10) -> list[AuthorityHit] | None:
    registry = await _load_registry()
    adapter = registry.get(source_id)
    if not adapter:
        return None
    return await adapter.search(query, limit)


async def fetch(source_id: str, external_id: str) -> AuthorityHit | None:
    registry = await _load_registry()
    adapter = registry.get(source_id)
    if not adapter:
        return None
    return await adapter.fetch(external_id)
