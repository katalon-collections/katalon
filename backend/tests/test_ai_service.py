from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from katalon.services.ai_service import (
    _build_messages,
    _coerce_value,
    _extract_content,
    _strip_code_fences,
)


def make_field(field_type: str, *, is_repeatable: bool = False) -> SimpleNamespace:
    return SimpleNamespace(field_type=field_type, is_repeatable=is_repeatable)


def test_strip_code_fences() -> None:
    raw = """```json
{"value":"abc"}
```"""
    assert _strip_code_fences(raw) == '{"value":"abc"}'


def test_extract_content_from_parts() -> None:
    content = [
        {"type": "text", "text": '{"value":"abc"}'},
        {"type": "ignored", "foo": "bar"},
    ]
    assert _extract_content(content) == '{"value":"abc"}'


def test_coerce_value_repeatable_requires_list() -> None:
    with pytest.raises(HTTPException):
        _coerce_value(make_field("text", is_repeatable=True), "abc")


def test_coerce_value_boolean_from_string() -> None:
    assert _coerce_value(make_field("boolean"), "true") is True


def test_coerce_value_number_from_string() -> None:
    assert _coerce_value(make_field("number"), "42") == 42


def test_group_ai_uses_only_requested_instance() -> None:
    record = SimpleNamespace(
        metadata_={
            "parts": [
                {"name": "Vorderseite", "description": "Alt vorne"},
                {"name": "Rückseite", "description": "Alt hinten"},
            ],
        }
    )
    field = SimpleNamespace(
        name="description",
        label={"de": "Beschreibung"},
        field_type="text",
        is_repeatable=False,
        settings={},
        target_type="object",
    )

    instance = record.metadata_["parts"][1]
    messages = _build_messages(
        field,
        record,
        {"prompt": "Beschreiben", "send_existing_value": True},
        None,
        100,
        instance,
    )
    prompt = messages[-1]["content"]

    assert '"group_context": {"name": "Rückseite"}' in prompt
    assert '"current_value": "Alt hinten"' in prompt
    assert "Vorderseite" not in prompt
