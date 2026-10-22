# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import importlib
import logging
from collections.abc import Callable
from functools import partial

from katalon.integrations.aat_adapter import AATAdapter
from katalon.integrations.authority import AuthorityHit, AuthoritySource
from katalon.integrations.geonames_adapter import GeonamesAdapter
from katalon.integrations.gnd_adapter import GNDAdapter
from katalon.integrations.iconclass_adapter import ICONCLASSAdapter
from katalon.integrations.tgn_adapter import TGNAdapter
from katalon.integrations.viaf_adapter import VIAFAdapter
from katalon.integrations.wikidata_adapter import WikidataAdapter

logger = logging.getLogger(__name__)

# Factories keep DB overrides local to each lookup.
_BUILTIN: dict[str, Callable[[], AuthoritySource]] = {
    "gnd":         GNDAdapter,
    "gnd-person":  partial(GNDAdapter, filter_type="type:Person", source_id="gnd-person"),
    "gnd-subject": partial(GNDAdapter, filter_type="type:SubjectHeading", source_id="gnd-subject"),
    "geonames":    GeonamesAdapter,
    "viaf":        VIAFAdapter,
    "wikidata":    WikidataAdapter,
    "tgn":         TGNAdapter,
    "iconclass":   ICONCLASSAdapter,
    "aat":         AATAdapter,
}

_LABELS: dict[str, str] = {
    "gnd":         "GND (Gemeinsame Normdatei)",
    "gnd-person":  "GND – Personennormdaten",
    "gnd-subject": "GND – Sachschlagwörter",
    "geonames":    "GeoNames",
    "viaf":        "VIAF",
    "wikidata":    "Wikidata",
    "tgn":         "Getty TGN (Thesaurus of Geographic Names)",
    "iconclass":   "Iconclass",
    "aat":         "Getty AAT (Art & Architecture Thesaurus)",
}


def default_label(source_id: str) -> str:
    return _LABELS.get(source_id, source_id.upper())


def default_adapter_class(source_id: str) -> str | None:
    adapter = _BUILTIN.get(source_id)
    if adapter is None:
        return None
    cls = type(adapter())
    return f"{cls.__module__}.{cls.__qualname__}"


async def _load_registry() -> dict[str, AuthoritySource]:
    """Load enabled adapters from authority_sources table, fall back to builtins."""
    try:
        from sqlalchemy import select

        from katalon.core.isolated_session import isolated_session
        from katalon.core.models import AuthoritySource as AuthoritySourceModel

        async with isolated_session("katalon-registry") as session:
            result = await session.execute(select(AuthoritySourceModel))
            db_sources = result.scalars().all()

        # Start with all builtins, then apply DB overrides (including disabling)
        registry = {key: factory() for key, factory in _BUILTIN.items()}
        for src in db_sources:
            if not src.is_enabled:
                registry.pop(src.id, None)
                continue
            if src.id in _BUILTIN:
                adapter = registry[src.id]
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
                    cfg = dict(src.config or {})
                    if issubclass(cls, GNDAdapter) and "source_id" not in cfg:
                        cfg["source_id"] = src.id
                    registry[src.id] = cls(**cfg)
                except Exception:
                    logger.warning("Failed to load authority adapter %r", src.id, exc_info=True)
        return registry
    except Exception:
        logger.warning("Failed to load authority sources from DB, using builtins only", exc_info=True)
        return {key: factory() for key, factory in _BUILTIN.items()}


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
