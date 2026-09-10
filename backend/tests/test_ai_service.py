# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import json
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from PIL import Image

from katalon import config
from katalon.services.ai_service import (
    _build_messages,
    _coerce_value,
    _enforce_input_token_limit,
    _extract_content,
    _prepare_vision_image,
    _strip_code_fences,
)
from katalon.services.schema_ai_service import SYSTEM_PROMPT, _extract_json_object, _parse_response


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


def test_vision_image_is_resized_to_1024px_jpeg(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config.settings, "media_root", str(tmp_path))
    path = tmp_path / "primary.png"
    Image.new("RGB", (2048, 1024), "red").save(path)

    image_bytes, mime_type = _prepare_vision_image(SimpleNamespace(storage_key="primary.png"))

    assert mime_type == "image/jpeg"
    with Image.open(BytesIO(image_bytes)) as image:
        assert image.size == (1024, 512)


def test_vision_image_with_alpha_remains_png(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config.settings, "media_root", str(tmp_path))
    path = tmp_path / "primary.png"
    Image.new("RGBA", (2048, 1024), (255, 0, 0, 128)).save(path)

    image_bytes, mime_type = _prepare_vision_image(SimpleNamespace(storage_key="primary.png"))

    assert mime_type == "image/png"
    with Image.open(BytesIO(image_bytes)) as image:
        assert image.size == (1024, 512)


def test_input_token_limit_is_enforced() -> None:
    with pytest.raises(HTTPException, match="Input-Token-Limit"):
        _enforce_input_token_limit(101, 100)


def test_extract_json_object_ignores_prose_prefix_and_suffix() -> None:
    raw = 'Hier ist mein Vorschlag: {"reply": "ok", "proposal": null}. Viel Erfolg!'
    assert _extract_json_object(raw) == '{"reply": "ok", "proposal": null}'


def test_extract_json_object_handles_nested_braces_and_escapes() -> None:
    raw = (
        '{"reply": "Enthält { und \\" } im Text", '
        '"proposal": {"fields": [{"settings": {"regex": "a{3}"}}]}} plus Nachsatz'
    )
    extracted = _extract_json_object(raw)
    parsed = json.loads(extracted)
    assert parsed["proposal"]["fields"][0]["settings"]["regex"] == "a{3}"
    assert not extracted.endswith("plus Nachsatz")


def test_extract_json_object_returns_text_without_brace() -> None:
    assert _extract_json_object("kein json hier") == "kein json hier"


def test_parse_response_accepts_plain_and_prose_wrapped_json() -> None:
    assert _parse_response('{"reply": "ok", "proposal": null}')["reply"] == "ok"
    assert _parse_response('Hier: {"reply": "ok", "proposal": null} Ende')["reply"] == "ok"


def test_parse_response_rejects_invalid_json() -> None:
    with pytest.raises(HTTPException, match="kein gültiges JSON"):
        _parse_response("das war keine JSON-Antwort")


def test_schema_prompt_asks_clarifying_questions() -> None:
    assert '"proposal": null' in SYSTEM_PROMPT
    assert "Rückfragen" in SYSTEM_PROMPT
    assert "Antwortbeispielen" in SYSTEM_PROMPT


def test_schema_prompt_place_normdata_belongs_to_place_not_object() -> None:
    assert "GND" in SYSTEM_PROMPT
    assert "Normdaten" in SYSTEM_PROMPT
    assert "Herstellungsort" in SYSTEM_PROMPT
    assert "place_fields" in SYSTEM_PROMPT
    assert "KEIN authority-Feld am Objekt" in SYSTEM_PROMPT
    assert "Normdaten gehören an den verknüpften Datensatz" in SYSTEM_PROMPT
    assert "target_type=\"place\"" in SYSTEM_PROMPT


def test_schema_prompt_embeds_ddb_field_list_as_model_knowledge() -> None:
    assert "Objekttitel oder -benennung" in SYSTEM_PROMPT
    assert "Inventarnummer" in SYSTEM_PROMPT
    assert "Ereignis in der Objektgeschichte" in SYSTEM_PROMPT
    assert "Alternativtext" in SYSTEM_PROMPT
    assert "sta.dnb.de" in SYSTEM_PROMPT
    assert "gnd.network" in SYSTEM_PROMPT
    assert "KEINE" in SYSTEM_PROMPT
    assert "Links" in SYSTEM_PROMPT


def test_schema_prompt_supports_relation_type_vocabularies() -> None:
    assert "relation_type_vocab" in SYSTEM_PROMPT
    assert 'kind="relation"' in SYSTEM_PROMPT
    assert "fotografiert_von" in SYSTEM_PROMPT
    assert "entstanden_in" in SYSTEM_PROMPT


def test_schema_prompt_avoids_soft_deleted_field_names() -> None:
    assert "used_field_names" in SYSTEM_PROMPT
    assert "datierung_2" in SYSTEM_PROMPT


def test_schema_prompt_models_companies_as_entity_relation() -> None:
    assert "Werbefirma" in SYSTEM_PROMPT
    assert 'target_type="entity"' in SYSTEM_PROMPT
    assert "NICHT als Textfeld" in SYSTEM_PROMPT
    assert "NICHT als" in SYSTEM_PROMPT
    assert "Vokabular-Feld" in SYSTEM_PROMPT


def test_schema_prompt_uses_edtf_date_capabilities() -> None:
    assert "EDTF" in SYSTEM_PROMPT
    assert "1900/1950" in SYSTEM_PROMPT
    assert "1920~" in SYSTEM_PROMPT
    assert "KEINE Gruppe" in SYSTEM_PROMPT


def test_schema_prompt_never_proposes_title_field() -> None:
    assert "eigenes Feld für Titel" in SYSTEM_PROMPT
    assert "label-Feld diese Rolle" in SYSTEM_PROMPT


def test_schema_prompt_models_events_works_as_occurrence_relation() -> None:
    assert 'target_type="occurrence"' in SYSTEM_PROMPT
    assert "Ereignisse" in SYSTEM_PROMPT
    assert "FRBR" in SYSTEM_PROMPT
    assert "Ausstellung" in SYSTEM_PROMPT
    assert "Unterscheide Typ und Instanz" in SYSTEM_PROMPT
