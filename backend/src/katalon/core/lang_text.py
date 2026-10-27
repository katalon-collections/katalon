# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin


def resolve_lang_text(value: dict[str, str] | None, preferred: str = "de") -> str:
    """Pick one string out of a {"de": ..., "en": ...} field for non-i18n-aware consumers."""
    if not value:
        return ""
    return value.get(preferred) or next(iter(value.values()), "")
