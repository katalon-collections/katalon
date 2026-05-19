import io

import openpyxl

from katalon.services.importer_service import (
    apply_mapping,
    detect_delimiter,
    dry_run,
    parse_csv,
    parse_excel,
)


def _make_xlsx(headers: list[str], rows: list[list]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_parse_excel_basic() -> None:
    data = _make_xlsx(["title", "creator"], [["Foto 1", "Maier"], ["Foto 2", "Huber"]])
    headers, rows = parse_excel(data)
    assert headers == ["title", "creator"]
    assert len(rows) == 2
    assert rows[0]["title"] == "Foto 1"
    assert rows[1]["creator"] == "Huber"


def test_parse_excel_empty_sheet() -> None:
    wb = openpyxl.Workbook()
    buf = io.BytesIO()
    wb.save(buf)
    headers, rows = parse_excel(buf.getvalue())
    assert headers == []
    assert rows == []


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
    records, idnos = apply_mapping(rows, mapping)
    # Without field_defs, fields are treated as non-repeatable -> single dict
    assert records[0]["title"] == {"value": "Foto 1"}
    assert records[0]["photographer"] == {"value": "Maier"}
    assert idnos[0] is None


def test_apply_mapping_with_split_transform_repeatable() -> None:
    """Split transform with is_repeatable=True should produce a list."""
    rows = [{"languages": "Deutsch, Englisch, Französisch"}]
    mapping = {"languages": {"target": "languages", "transforms": [{"type": "split", "delimiter": ",", "filter_empty": True}]}}
    # Mock field_defs with is_repeatable=True
    class MockField:
        field_type = "text"
        is_repeatable = True
    records, idnos = apply_mapping(rows, mapping, {"languages": MockField()})
    assert records[0]["languages"] == [{"value": "Deutsch"}, {"value": "Englisch"}, {"value": "Französisch"}]


def test_apply_mapping_with_dict_target() -> None:
    rows = [{"title": "Foto 1"}]
    mapping = {"title": {"target": "title"}}
    records, idnos = apply_mapping(rows, mapping)
    assert records[0]["title"] == {"value": "Foto 1"}


def test_apply_transforms_replace() -> None:
    from katalon.services.importer_service import apply_transforms
    result = apply_transforms("Hello World", [{"type": "replace", "search": "World", "replace": "Katalon", "case_sensitive": True}])
    assert result == ["Hello Katalon"]


def test_apply_transforms_regex_extract() -> None:
    from katalon.services.importer_service import apply_transforms
    result = apply_transforms("Jahr: 1996", [{"type": "regex_extract", "pattern": r"\d{4}", "group": 0}])
    assert result == ["1996"]


def test_apply_transforms_vocab_map() -> None:
    from katalon.services.importer_service import apply_transforms
    result = apply_transforms("DE", [{"type": "vocab_map", "vocab_map": {"DE": "Deutsch", "EN": "Englisch"}, "strict": False}])
    assert result == ["Deutsch"]


def test_apply_transforms_expression() -> None:
    from katalon.services.importer_service import apply_transforms
    # Jinja2 syntax
    result = apply_transforms("hello", [{"type": "expression", "expression": "{{ value | upper }}"}])
    assert result == ["HELLO"]
    # Backward compat: bare ${value} still works
    result2 = apply_transforms("world", [{"type": "expression", "expression": "prefix_${value}_suffix"}])
    assert result2 == ["prefix_world_suffix"]


def test_apply_transforms_pipeline() -> None:
    from katalon.services.importer_service import apply_transforms
    result = apply_transforms("  a, b, c  ", [
        {"type": "trim"},
        {"type": "split", "delimiter": ",", "filter_empty": True},
    ])
    assert result == ["a", "b", "c"]


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
    assert result["errors"][0]["row"] == 2  # row 1 is the header; first data row is row 2
