# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""License / rights-statement URIs: display labels and spelling normalization.

Katalon prefers no spelling of a license URI (http vs. https, trailing slash).
An export keeps the stored spelling unless its configuration lists allowed URIs
(``institution_config.allowed_license_uris``); then a stored URI is written in
the spelling of the matching list entry, because aggregators compare literally.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

_CC_VERSIONS = ("4.0", "3.0")
_CC_LICENSES = ("by", "by-sa", "by-nd", "by-nc", "by-nc-sa", "by-nc-nd")
_RS_STATEMENTS = ("InC", "InC-EDU", "InC-OW-EU", "NoC-NC", "NoC-OKLR", "NKC", "CNE", "UND")

# Source attribute for rightsType/conceptID.
_SOURCE_BY_HOST = {"creativecommons.org": "CC", "rightsstatements.org": "RightsStatements.org"}


def comparable(uri: str) -> str:
    """Spelling-independent key: no scheme, no www, no legalcode/deed suffix, no trailing slash."""
    value = re.sub(r"^https?://(www\.)?", "", uri.strip(), flags=re.I)
    value = re.sub(r"/(legalcode|deed\.[a-z-]+)$", "", value, flags=re.I)
    return value.rstrip("/").lower()


# Display labels, keyed spelling-independently.
_LABELS: dict[str, str] = {
    comparable("creativecommons.org/publicdomain/zero/1.0/"): "CC0 1.0",
    comparable("creativecommons.org/publicdomain/mark/1.0/"): "Public Domain Mark 1.0",
    **{
        comparable(f"creativecommons.org/licenses/{lic}/{ver}/"): f"CC {lic.upper()} {ver}"
        for ver in _CC_VERSIONS
        for lic in _CC_LICENSES
    },
    **{comparable(f"rightsstatements.org/vocab/{rs}/1.0/"): rs for rs in _RS_STATEMENTS},
}


def license_label(uri: str | None) -> str | None:
    return _LABELS.get(comparable(uri)) if uri else None


def license_source(uri: str | None) -> str | None:
    match = re.match(r"^https?://(?:www\.)?([^/]+)/", (uri or "").strip(), flags=re.I)
    return _SOURCE_BY_HOST.get(match.group(1).lower()) if match else None


def normalize_license_uri(uri: str | None, allowed: Iterable[str] = ()) -> str | None:
    """Trimmed URI; with an allowed list, written in the spelling of the matching entry."""
    value = (uri or "").strip()
    if not value:
        return None
    key = comparable(value)
    return next((entry.strip() for entry in allowed if comparable(entry) == key), value)


def is_allowed_license(uri: str | None, allowed: Iterable[str]) -> bool:
    """Literal comparison (after normalize_license_uri) against the configured list."""
    entries = {entry.strip() for entry in allowed if entry and entry.strip()}
    return bool(uri) and uri in entries
