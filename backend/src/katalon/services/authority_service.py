from __future__ import annotations

import importlib

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
}

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
            result = await session.execute(
                select(AuthoritySourceModel).where(AuthoritySourceModel.is_enabled.is_(True))
            )
            db_sources = result.scalars().all()

        # Start with all builtins, then apply DB overrides for enabled sources
        registry: dict[str, AuthoritySource] = dict(_BUILTIN)
        for src in db_sources:
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
