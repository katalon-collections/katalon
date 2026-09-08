# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import lxml.etree

logger = logging.getLogger(__name__)

_SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas" / "lido"
_LIDO_XSD_PATH = _SCHEMA_DIR / "lido-v1.0.xsd"
_XML_XSD_PATH = _SCHEMA_DIR / "xml.xsd"
_GML_XSD_PATH = _SCHEMA_DIR / "gml.xsd"

_cached_schema: lxml.etree.XMLSchema | None = None


class _OfflineResolver(lxml.etree.Resolver):
    def resolve(self, url: str, pubid: str, context: Any) -> Any:
        if "xml.xsd" in url:
            if _XML_XSD_PATH.exists():
                return self.resolve_filename(str(_XML_XSD_PATH), context)
        if "gml" in url or "feature.xsd" in url:
            if _GML_XSD_PATH.exists():
                return self.resolve_filename(str(_GML_XSD_PATH), context)
        return None


def get_lido_schema() -> lxml.etree.XMLSchema | None:
    global _cached_schema
    if _cached_schema is not None:
        return _cached_schema

    if not _LIDO_XSD_PATH.exists():
        logger.warning("LIDO 1.0 XSD not found at %s", _LIDO_XSD_PATH)
        return None

    try:
        parser = lxml.etree.XMLParser()
        parser.resolvers.add(_OfflineResolver())
        schema_doc = lxml.etree.parse(str(_LIDO_XSD_PATH), parser)
        _cached_schema = lxml.etree.XMLSchema(schema_doc)
    except Exception:
        logger.error("Failed to compile LIDO 1.0 XMLSchema", exc_info=True)
        _cached_schema = None
    return _cached_schema


def validate_lido_xml(xml_content: str | bytes | Any) -> list[str]:
    """Validate LIDO XML string/bytes/element against the bundled LIDO 1.0 XMLSchema.

    Returns a list of error messages (empty if valid).
    """
    schema = get_lido_schema()
    if schema is None:
        return ["LIDO XMLSchema could not be loaded."]

    try:
        if isinstance(xml_content, str):
            doc = lxml.etree.fromstring(xml_content.encode("utf-8"))
        elif isinstance(xml_content, bytes):
            doc = lxml.etree.fromstring(xml_content)
        elif hasattr(xml_content, "tag"):
            # xml.etree.ElementTree.Element -> serialize and parse with lxml
            import xml.etree.ElementTree as ET

            raw = ET.tostring(xml_content, encoding="utf-8")
            doc = lxml.etree.fromstring(raw)
        else:
            doc = xml_content

        if not schema.validate(doc):
            return [str(err) for err in schema.error_log]
        return []
    except Exception as e:
        return [f"XML parsing error during LIDO validation: {e}"]
