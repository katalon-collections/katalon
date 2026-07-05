from katalon.core.models import VocabularyTerm
from katalon.services.vocabulary_import_service import (
    _add_authority,
    parse_csv_terms,
    parse_json_terms,
)


def test_add_authority_appends_and_dedupes() -> None:
    term = VocabularyTerm(term="drm", label={}, inverse_label={}, metadata_={})

    _add_authority(term, "gnd", "4149094-6")
    assert term.metadata_["authorities"] == [
        {"source": "gnd", "external_id": "4149094-6", "label": ""}
    ]

    # Second source is added
    _add_authority(term, "wikidata", "Q234")
    assert len(term.metadata_["authorities"]) == 2

    # Same source+id is not duplicated
    _add_authority(term, "gnd", "4149094-6")
    assert len(term.metadata_["authorities"]) == 2


def test_parse_csv_terms_with_mapping_and_parent() -> None:
    content = (
        "term;label_de;label_en;parent_term;external_id\n"
        "foto;Foto;Photo;;gnd-1\n"
        "portrait;Porträt;Portrait;foto;gnd-2\n"
    ).encode()
    mapping = {
        "term": "term",
        "label_de": "label:de",
        "label_en": "label:en",
        "parent_term": "parent_term",
        "external_id": "external_id",
    }

    terms, errors = parse_csv_terms(content, mapping)

    assert errors == []
    assert len(terms) == 2
    assert terms[0].label == {"de": "Foto", "en": "Photo"}
    assert terms[1].parent_term == "foto"


def test_parse_csv_terms_requires_term() -> None:
    content = b"label_de\nOhne Term\n"
    mapping = {"label_de": "label:de"}

    terms, errors = parse_csv_terms(content, mapping)

    assert terms == []
    assert errors[0]["row"] == 2
    assert "term" in errors[0]["message"]


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
