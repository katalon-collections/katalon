# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import secrets

from katalon.config import settings

_ALPHABET = "abcdefghijklmnopqrstuvwxyz234567"


class ArkAdapterError(Exception):
    pass


class ArkAdapter:
    """Mints ARK identifiers locally.

    ARK needs no central registrar: the identifier is just
    ``ark:/{naan}/{suffix}`` and can be minted offline. Resolution runs through
    n2t.net once a production NAAN is registered; the reserved test NAAN
    ``99999`` intentionally does not resolve.
    """

    def __init__(self) -> None:
        self.naan = settings.ark_naan
        self.suffix_length = settings.ark_suffix_length

    def ensure_configured(self) -> None:
        if not settings.ark_enabled:
            raise ArkAdapterError("ARK ist deaktiviert.")
        if not self.naan:
            raise ArkAdapterError("ARK ist unvollständig konfiguriert. Bitte ARK_NAAN setzen.")

    def mint(self) -> str:
        self.ensure_configured()
        suffix = "".join(secrets.choice(_ALPHABET) for _ in range(self.suffix_length))
        return f"ark:/{self.naan}/{suffix}"


def ark_resolver_link(ark: str) -> str:
    return f"{settings.ark_resolver_url.rstrip('/')}/{ark}"
