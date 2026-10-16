# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Canonical Linked-Data URIs for authority identifiers.

One place for all exporters (LIDO, JSON-LD, EAD, METS): an authority value
``{source, external_id}`` or a pasted authority URL becomes the URI form that
Linked-Data consumers resolve.
"""

from __future__ import annotations

import re

# source id -> URI template. GeoNames needs the trailing slash (Linked-Data form,
# GeoNames' own semantic URI form; without it the URI does not resolve as RDF).
_URI_TEMPLATES: dict[str, str] = {
    "gnd": "https://d-nb.info/gnd/{id}",
    "wikidata": "http://www.wikidata.org/entity/{id}",
    "aat": "http://vocab.getty.edu/aat/{id}",
    "tgn": "http://vocab.getty.edu/tgn/{id}",
    "ulan": "http://vocab.getty.edu/ulan/{id}",
    "viaf": "http://viaf.org/viaf/{id}",
    "geonames": "https://sws.geonames.org/{id}/",
    "iconclass": "https://iconclass.org/{id}",
}

# Display names for lido:source and similar attributes.
_SOURCE_LABELS: dict[str, str] = {
    "gnd": "GND",
    "wikidata": "Wikidata",
    "aat": "AAT",
    "tgn": "TGN",
    "ulan": "ULAN",
    "viaf": "VIAF",
    "geonames": "GeoNames",
    "iconclass": "Iconclass",
}

# Katalon authority sources that are flavours of one authority file.
_SOURCE_ALIASES: dict[str, str] = {"gnd-person": "gnd", "gnd-subject": "gnd"}

# Recognised URL forms -> (source, id). Order matters only for readability.
_URL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("gnd", re.compile(r"^https?://(?:www\.)?d-nb\.info/gnd/([0-9X-]+)/?$", re.I)),
    ("gnd", re.compile(r"^https?://lobid\.org/gnd/([0-9X-]+)(?:\.json)?/?$", re.I)),
    ("wikidata", re.compile(r"^https?://(?:www\.)?wikidata\.org/(?:wiki|entity)/(Q\d+)/?$", re.I)),
    ("aat", re.compile(r"^https?://vocab\.getty\.edu/(?:page/)?aat/(\d+)(?:\.json)?/?$", re.I)),
    ("tgn", re.compile(r"^https?://vocab\.getty\.edu/(?:page/)?tgn/(\d+)(?:\.json)?/?$", re.I)),
    ("ulan", re.compile(r"^https?://vocab\.getty\.edu/(?:page/)?ulan/(\d+)(?:\.json)?/?$", re.I)),
    ("viaf", re.compile(r"^https?://(?:www\.)?viaf\.org/viaf/(\d+)/?$", re.I)),
    ("geonames", re.compile(r"^https?://(?:sws\.|www\.)?geonames\.org/(\d+)(?:/.*)?$", re.I)),
    ("iconclass", re.compile(r"^https?://(?:www\.)?iconclass\.org/([^/?#]+)/?$", re.I)),
]

# Formal shape of identifiers per source. Iconclass notations start with a digit
# (main divisions 0-9); values like "de" (left over from a broken import) get no URI.
_ID_PATTERNS: dict[str, re.Pattern[str]] = {
    "gnd": re.compile(r"^[0-9]+[0-9X-]*$"),
    "wikidata": re.compile(r"^Q\d+$"),
    "aat": re.compile(r"^\d+$"),
    "tgn": re.compile(r"^\d+$"),
    "ulan": re.compile(r"^\d+$"),
    "viaf": re.compile(r"^\d+$"),
    "geonames": re.compile(r"^\d+$"),
    "iconclass": re.compile(r"^\d[0-9A-Z()+.,: '-]*$"),
}


def normalize_source(source: str | None) -> str:
    key = (source or "").strip().lower()
    return _SOURCE_ALIASES.get(key, key)


def source_label(source: str | None) -> str | None:
    """Display name of an authority source for lido:source (GND, Wikidata, ...)."""
    key = normalize_source(source)
    if not key:
        return None
    return _SOURCE_LABELS.get(key, (source or "").strip())


def authority_uri(source: str | None, external_id: str | None) -> str | None:
    """Return the canonical URI for an authority identifier, or None if unknown/invalid."""
    key = normalize_source(source)
    ident = (external_id or "").strip()
    if not key or not ident:
        return None
    if ident.lower().startswith(("http://", "https://")):
        parsed = parse_authority_url(ident)
        return parsed[1] if parsed and parsed[0] == key else None
    template = _URI_TEMPLATES.get(key)
    if template is None:
        return None
    pattern = _ID_PATTERNS.get(key)
    if pattern is not None and not pattern.match(ident):
        return None
    return template.format(id=ident)


def parse_authority_url(url: str | None) -> tuple[str, str] | None:
    """Recognise an authority URL and return (source, canonical URI)."""
    value = (url or "").strip()
    for source, pattern in _URL_PATTERNS:
        if match := pattern.match(value):
            uri = authority_uri(source, match.group(1))
            return (source, uri) if uri else None
    return None
