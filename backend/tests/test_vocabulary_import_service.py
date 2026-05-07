from katalon.services.vocabulary_import_service import parse_csv_terms, parse_json_terms


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
