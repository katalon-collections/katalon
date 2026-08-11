from katalon.services.vocabulary_import_service import (
    parse_csv_terms,
    parse_json_terms,
)


def test_parse_csv_terms_with_mapping_and_parent() -> None:
    content = (
        "term;label_de;label_en;parent_term\n"
        "foto;Foto;Photo;\n"
        "portrait;Porträt;Portrait;foto\n"
    ).encode()
    mapping = {
        "term": "term",
        "label_de": "label:de",
        "label_en": "label:en",
        "parent_term": "parent_term",
    }

    terms, errors = parse_csv_terms(content, mapping)

    assert errors == []
    assert len(terms) == 2
    assert terms[0].label == {"de": "Foto", "en": "Photo"}
    assert terms[1].parent_term == "foto"


def test_parse_csv_terms_requires_term_or_label() -> None:
    content = b"col_a\nOhne Mapping\n"
    mapping = {"col_a": "external_id"}

    terms, errors = parse_csv_terms(content, mapping)

    assert terms == []
    assert errors[0]["row"] == 2
    assert "term" in errors[0]["message"]


def test_parse_csv_terms_slugifies_term_from_label() -> None:
    content = (
        b"bezeichnung;oberbegriff\n"
        b"Kopierschutz;\n"
        b"Kopierschutz DRM;Kopierschutz\n"
        b"Wasserzeichen/Markierung;Kopierschutz\n"
    )
    mapping = {"bezeichnung": "label:de", "oberbegriff": "parent_term"}

    terms, errors = parse_csv_terms(content, mapping)

    assert errors == []
    assert [t.term for t in terms] == [
        "kopierschutz",
        "kopierschutz-drm",
        "wasserzeichen-markierung",
    ]
    assert terms[1].parent_term == "Kopierschutz"
    assert terms[0].label == {"de": "Kopierschutz"}


def test_parse_json_terms_slugifies_term_from_label() -> None:
    content = b"""
    [
      {"label": {"de": "Kopierschutz"}, "children": [
        {"label": "Kopierschutz DRM"}
      ]}
    ]
    """

    terms, errors = parse_json_terms(content)

    assert errors == []
    assert {t.term for t in terms} == {"kopierschutz", "kopierschutz-drm"}
    child = [t for t in terms if t.term == "kopierschutz-drm"][0]
    assert child.parent_term == "kopierschutz"


def test_parse_csv_terms_trims_whitespace_in_headers_and_values() -> None:
    """CSV with spaces after commas and trailing spaces in headers/values."""
    content = (
        "639-1 ,639-2/T ,639-2/B ,Language name ,Native name \n"
        "aa ,aar ,aar ,Afar ,Afaraf \n"
        "ab ,abk ,abk ,Abkhaz ,\"аҧсуа бызшәа, аҧсшәа \" \n"
    ).encode()
    mapping = {
        "639-2/T": "term",
        "Language name": "label:de",
    }

    terms, errors = parse_csv_terms(content, mapping)

    assert errors == []
    assert len(terms) == 2
    assert terms[0].term == "aar"
    assert terms[0].label == {"de": "Afar"}
    assert terms[1].term == "abk"
    assert terms[1].label == {"de": "Abkhaz"}


def test_parse_json_terms_nested_hierarchy() -> None:
    content = b"""
    [
      {"term": "kunst", "label": {"de": "Kunst"}, "children": [
        {"term": "malerei", "label": {"de": "Malerei"}}
      ]}
    ]
    """

    terms, errors = parse_json_terms(content)

    assert errors == []
    assert len(terms) == 2
    child = [t for t in terms if t.term == "malerei"][0]
    assert child.parent_term == "kunst"
