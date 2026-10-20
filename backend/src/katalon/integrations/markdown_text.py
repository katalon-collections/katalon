# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Plain text from the Markdown that `richtext` fields store.

Export formats (LIDO, METS/MODS, Dublin Core) carry plain text, so formatting syntax
must not leak into them: emphasis and heading markers, link syntax, hard-break
backslashes and backslash escapes are removed, the text itself is kept.
"""

from __future__ import annotations

import re

# Backslash escapes are parked in private-use characters so the markup patterns
# below never touch escaped (literal) characters.
_ESCAPE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!<>|~])")
_PARK_BASE = 0xE000
_HARD_BREAK = re.compile(r"\\\n| {2,}\n")
_HEADING = re.compile(r"^[ \t]{0,3}#{1,6}[ \t]+", re.MULTILINE)
_QUOTE = re.compile(r"^[ \t]{0,3}>[ \t]?", re.MULTILINE)
_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_STRONG = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1", re.DOTALL)
_EMPH = re.compile(r"(?<![\w*])([*_])(?=\S)(.+?)(?<=\S)\1(?![\w*])", re.DOTALL)
_CODE = re.compile(r"`([^`]*)`")


def markdown_to_plain_text(value: str) -> str:
    text = _HARD_BREAK.sub("\n", value)
    text = _ESCAPE.sub(lambda m: chr(_PARK_BASE + ord(m.group(1))), text)
    text = _HEADING.sub("", text)
    text = _QUOTE.sub("", text)
    text = _LINK.sub(r"\1", text)
    text = _STRONG.sub(r"\2", text)
    text = _EMPH.sub(r"\2", text)
    text = _CODE.sub(r"\1", text)
    return re.sub(r"[-]", lambda m: chr(ord(m.group(0)) - _PARK_BASE), text)
