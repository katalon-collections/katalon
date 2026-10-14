# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""URL values reach the index in one shape (grp_* is mapped dynamically)."""

import uuid
from types import SimpleNamespace

from katalon.services.search_service import normalize_url_values


def _field(name: str, field_type: str, parent_id=None) -> SimpleNamespace:
    return SimpleNamespace(id=uuid.uuid4(), name=name, field_type=field_type, parent_id=parent_id)


group = _field("weblinks", "group")
fields = [
    _field("homepage", "url"),
    _field("sources", "url"),
    _field("title", "text"),
    group,
    _field("link", "url", group.id),
    _field("note", "text", group.id),
]


def test_top_level_and_group_urls_get_one_shape() -> None:
    md = {
        "homepage": " https://a.org ",
        "sources": [{"value": "https://b.org", "label": "B"}, "https://c.org", {"value": ""}],
        "title": "https://not-a-url-field.org",
        "weblinks": [
            {"link": "https://d.org", "note": "x"},
            {"link": {"value": "https://e.org", "label": ""}},
            {"link": "", "note": "leer"},
        ],
    }
    out = normalize_url_values(md, fields)
    assert out["homepage"] == {"value": "https://a.org"}
    assert out["sources"] == [{"value": "https://b.org", "label": "B"}, {"value": "https://c.org"}]
    assert out["title"] == "https://not-a-url-field.org"
    assert out["weblinks"] == [
        {"link": {"value": "https://d.org"}, "note": "x"},
        {"link": {"value": "https://e.org"}},
        {"note": "leer"},
    ]
    # Input is not mutated.
    assert md["weblinks"][0]["link"] == "https://d.org"


def test_empty_url_fields_are_dropped_and_no_url_schema_is_a_noop() -> None:
    assert "homepage" not in normalize_url_values({"homepage": {"value": "  "}}, fields)
    md = {"title": "x"}
    assert normalize_url_values(md, [_field("title", "text")]) is md
