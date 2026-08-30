import json

from katalon.services.audit_service import _display_value, collapse_value, diff_fields


def test_collapse_value_parses_legacy_json_string() -> None:
    value = '{"id": "4a10884e-6b12-4914-8da5-aa05be7991ec", "label": "Glasnegativ"}'
    assert collapse_value(value) == "Glasnegativ"


def test_collapse_value_parses_legacy_json_string_list() -> None:
    value = '[{"value": "Straße in Marrakesch", "lang": "de"}]'
    assert collapse_value(value) == "Straße in Marrakesch"


def test_collapse_value_plain_string_unaffected() -> None:
    assert collapse_value("Glasnegativ") is None


def test_collapse_value_dict_without_label_unaffected() -> None:
    assert collapse_value({"entity_id": "4a10884e", "role": "Auftraggeber"}) is None


def test_display_value_empty() -> None:
    assert _display_value(None) is None


def test_display_value_primitives_pass_through() -> None:
    assert _display_value("foo") == "foo"
    assert _display_value(42) == 42
    assert _display_value(True) is True
    assert _display_value(1.5) == 1.5


def test_display_value_collapses_vocab_dict_to_label() -> None:
    value = {"id": "4a10884e-6b12-4914-8da5-aa05be7991ec", "label": "Glasnegativ"}
    assert _display_value(value) == "Glasnegativ"


def test_display_value_collapses_legacy_json_string_to_label() -> None:
    value = '{"id": "4a10884e", "label": "Glasnegativ"}'
    assert _display_value(value) == "Glasnegativ"


def test_display_value_collapses_i18n_list_to_values() -> None:
    value = [{"value": "Straße in Marrakesch", "lang": "de"}]
    assert _display_value(value) == "Straße in Marrakesch"


def test_display_value_collapses_string_list() -> None:
    assert _display_value(["rot", "grün"]) == "rot, grün"


def test_display_value_keeps_json_without_label() -> None:
    value = {"entity_id": "4a10884e", "role": "Auftraggeber"}
    assert _display_value(value) == '{"entity_id": "4a10884e", "role": "Auftraggeber"}'


def test_display_value_falls_back_to_json_for_mixed_list() -> None:
    value = [{"entity_id": "x", "role": "Auftraggeber"}, "unbekannt"]
    assert _display_value(value) == json.dumps(value, ensure_ascii=False)


def test_diff_fields_expands_metadata_with_collapsed_labels() -> None:
    old = {"metadata": {"material": {"id": "old-id", "label": "Glas"}}}
    new = {"metadata": {"material": {"id": "4a10884e", "label": "Glasnegativ"}}}
    diff = diff_fields(old, new)
    assert diff == {
        "old": {"metadata.material": "Glas"},
        "new": {"metadata.material": "Glasnegativ"},
    }


def test_read_path_collapses_legacy_json_string_diff() -> None:
    from katalon.api.v1.audit import _collapse_diff_values

    changed = {
        "old": {"metadata.material": None},
        "new": {"metadata.material": '{"id": "4a10884e", "label": "Glasnegativ"}'},
    }
    assert _collapse_diff_values(changed) == {
        "old": {"metadata.material": None},
        "new": {"metadata.material": "Glasnegativ"},
    }


def test_read_path_leaves_non_vocab_diff_untouched() -> None:
    from katalon.api.v1.audit import _collapse_diff_values

    changed = {"old": {"status": "draft"}, "new": {"status": "public"}}
    assert _collapse_diff_values(changed) == changed

    changed_none = None
    assert _collapse_diff_values(changed_none) is None
