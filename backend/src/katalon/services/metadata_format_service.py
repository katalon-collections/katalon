# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import importlib
import logging

from katalon.integrations.jsonld_format import JsonLdFormat
from katalon.integrations.lido_format import LidoFormat
from katalon.integrations.metadata_format import MetadataFormat
from katalon.integrations.mets_mods_format import MetsModsFormat
from katalon.integrations.oai_dc_format import OaiDcFormat

logger = logging.getLogger(__name__)

# Built-in formats always available (can be extended/overridden by a metadata_formats row).
_BUILTIN: dict[str, MetadataFormat] = {
    "oai_dc": OaiDcFormat(),
    "lido": LidoFormat(),
    "mets_mods": MetsModsFormat(),
    "json_ld": JsonLdFormat(),
}


def default_adapter_class(format_key: str) -> str | None:
    fmt = _BUILTIN.get(format_key)
    if fmt is None:
        return None
    cls = type(fmt)
    return f"{cls.__module__}.{cls.__qualname__}"


# Cache: format_key -> instance (populated lazily from DB)
_cache: dict[str, MetadataFormat] | None = None


async def _load_registry() -> dict[str, MetadataFormat]:
    """Load metadata_formats overrides/additions, fall back to builtins."""
    global _cache
    if _cache is not None:
        return _cache
    try:
        from sqlalchemy import select

        from katalon.core.models import MetadataFormat as MetadataFormatModel
        from katalon.database import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(MetadataFormatModel))
            db_formats = result.scalars().all()

        registry: dict[str, MetadataFormat] = dict(_BUILTIN)
        for row in db_formats:
            if row.id in _BUILTIN:
                fmt = _BUILTIN[row.id]
                for key, val in (row.config or {}).items():
                    if hasattr(fmt, key):
                        setattr(fmt, key, set(val) if key == "targets" else val)
                registry[row.id] = fmt
            else:
                try:
                    module_path, cls_name = row.adapter_class.rsplit(".", 1)
                    mod = importlib.import_module(module_path)
                    cls = getattr(mod, cls_name)
                    registry[row.id] = cls(**(row.config or {}))
                except Exception:
                    logger.warning(
                        "Failed to load custom metadata format %r (%s)",
                        row.id, row.adapter_class, exc_info=True,
                    )
        _cache = registry
    except Exception:
        logger.warning("Failed to load metadata_formats from DB, using builtins only", exc_info=True)
        _cache = dict(_BUILTIN)
    return _cache


def invalidate_cache() -> None:
    global _cache
    _cache = None


async def get_format(format_key: str) -> MetadataFormat | None:
    registry = await _load_registry()
    return registry.get(format_key)


async def list_formats() -> list[MetadataFormat]:
    registry = await _load_registry()
    return list(registry.values())
