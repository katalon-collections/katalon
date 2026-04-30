import pytest
from katalon.services.importer_service import detect_delimiter, parse_csv, apply_mapping, dry_run


def test_detect_delimiter_comma() -> None:
    assert detect_delimiter("a,b,c\n1,2,3") == ","


def test_detect_delimiter_semicolon() -> None:
    assert detect_delimiter("a;b;c\n1;2;3") == ";"


def test_parse_csv_basic() -> None:
    content = b"title,creator\nFoto 1,Maier\nFoto 2,Huber\n"
    headers, rows = parse_csv(content)
    assert headers == ["title", "creator"]
    assert len(rows) == 2
    assert rows[0]["title"] == "Foto 1"


def test_apply_mapping() -> None:
    rows = [{"title": "Foto 1", "creator": "Maier"}]
    mapping = {"title": "title", "creator": "photographer"}
    result = apply_mapping(rows, mapping)
    assert result[0]["title"] == [{"value": "Foto 1"}]
    assert result[0]["photographer"] == [{"value": "Maier"}]


def test_dry_run_no_errors() -> None:
    rows = [{"title": "Foto 1"}]
    mapping = {"title": "title"}
    result = dry_run(rows, mapping)
    assert result["total"] == 1
    assert result["valid"] == 1
    assert result["errors"] == []


def test_dry_run_empty_mapping() -> None:
    rows = [{"title": "Foto 1"}]
    mapping: dict = {}
    result = dry_run(rows, mapping)
    assert result["errors"][0]["row"] == 1
