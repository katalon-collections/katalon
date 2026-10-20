# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid
from types import SimpleNamespace

from katalon.integrations.markdown_text import markdown_to_plain_text
from katalon.services.export_context_service import _richtext_as_plain_text


def test_markup_is_removed_text_kept():
    assert markdown_to_plain_text("mit **fett** und *kursiv* [Link](https://x.de)") == "mit fett und kursiv Link"
    assert markdown_to_plain_text("#### Titel\n\nA\\\nB") == "Titel\n\nA\nB"


def test_escaped_characters_stay_literal():
    assert markdown_to_plain_text("Edition \\*IDEALE\\* os\\_ub 1914\\. Krieg") == "Edition *IDEALE* os_ub 1914. Krieg"
    assert markdown_to_plain_text("2*3 und a_b_c") == "2*3 und a_b_c"


def _fd(name, field_type, parent_id=None):
    return SimpleNamespace(id=uuid.uuid4(), name=name, field_type=field_type, parent_id=parent_id)


def test_export_context_plain_richtext_top_level_and_group():
    group = _fd("beschriftung", "group")
    defs = [
        _fd("kommentar", "richtext"),
        _fd("titel", "text"),
        group,
        _fd("vorder", "richtext", group.id),
        _fd("art", "text", group.id),
    ]
    fields = {
        "kommentar": ["**a**"],
        "titel": "*bleibt*",
        "beschriftung": [{"vorder": "x\\\ny", "art": "*bleibt*"}],
    }
    assert _richtext_as_plain_text(fields, defs) == {
        "kommentar": ["a"],
        "titel": "*bleibt*",
        "beschriftung": [{"vorder": "x\ny", "art": "*bleibt*"}],
    }
