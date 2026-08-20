from katalon.services.media_batch_import_service import (
    folder_or_filename_object_id,
    media_references_for_rows,
    normalize_filename,
    parse_mapping_csv,
)


def test_parse_mapping_csv_accepts_alias_columns() -> None:
    content = (
        b"Dateiname;Objekt_ID;Medientyp\n"
        b"foto1.jpg;550e8400-e29b-41d4-a716-446655440000;detail\n"
    )
    rows, errors = parse_mapping_csv(content)
    assert errors == []
    assert len(rows) == 1
    assert rows[0].filename == "foto1.jpg"
    assert rows[0].object_id == "550e8400-e29b-41d4-a716-446655440000"
    assert rows[0].media_type == "detail"


def test_parse_mapping_csv_requires_filename_and_object_id() -> None:
    rows, errors = parse_mapping_csv(b"foo,bar\nx,y\n")
    assert rows == []
    assert errors
    assert "filename" in str(errors[0]["message"])


def test_folder_or_filename_object_id_from_folder_name() -> None:
    object_id = folder_or_filename_object_id("550e8400-e29b-41d4-a716-446655440000/bild.jpg")
    assert object_id == "550e8400-e29b-41d4-a716-446655440000"


def test_folder_or_filename_object_id_from_filename_prefix() -> None:
    object_id = folder_or_filename_object_id("bilder/550e8400-e29b-41d4-a716-446655440000_01.jpg")
    assert object_id == "550e8400-e29b-41d4-a716-446655440000"


def test_normalize_filename_uses_basename_unicode_nfc_and_casefold() -> None:
    assert normalize_filename("ordner/Ru\u0308ckseite.JPG") == "rückseite.jpg"


def test_media_references_accept_repeated_xml_values() -> None:
    rows: list[dict[str, object]] = [
        {"resourceID": ["Vorderseite.jpg", "Rückseite.jpg", "Vorderseite.jpg"]},
        {"resourceID": ""},
    ]

    references, stats = media_references_for_rows(rows, "resourceID")

    assert references == [
        [("Vorderseite.jpg", "vorderseite.jpg"), ("Rückseite.jpg", "rückseite.jpg")],
        [],
    ]
    assert stats == {
        "selector_found": True,
        "objects": 1,
        "files": 2,
        "empty": 1,
        "conflicts": [],
    }


def test_media_references_block_same_normalized_filename_across_rows() -> None:
    rows: list[dict[str, object]] = [
        {"resourceID": "Ru\u0308ckseite.JPG"},
        {"resourceID": "rückseite.jpg"},
    ]

    _, stats = media_references_for_rows(rows, "resourceID")

    assert stats["conflicts"] == [{"filename": "rückseite.jpg", "rows": [2, 3]}]


def test_media_references_report_unknown_selector() -> None:
    _, stats = media_references_for_rows([{"resourceID": "image.jpg"}], "missing")

    assert stats["selector_found"] is False
