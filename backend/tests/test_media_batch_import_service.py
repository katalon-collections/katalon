from katalon.services.media_batch_import_service import (
    folder_or_filename_object_id,
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
