# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from katalon.services.importer.formats.csv_format import CsvFormat


def test_csv_windows_1252_keeps_umlauts() -> None:
    content = "ID;Namen für Vorkommnisse\nx_1;Größe\n".encode("cp1252")
    fmt = CsvFormat()
    assert [s.path for s in fmt.list_selectors(content)] == ["ID", "Namen für Vorkommnisse"]
    assert list(fmt.parse(content)) == [{"ID": "x_1", "Namen für Vorkommnisse": "Größe"}]


def test_csv_utf8_with_bom_still_works() -> None:
    content = "\ufeffID;Name\nx_1;Größe\n".encode()
    assert list(CsvFormat().parse(content)) == [{"ID": "x_1", "Name": "Größe"}]


def test_detect_encoding_for_utf8_bom_cp1252_and_undefined_bytes() -> None:
    from katalon.services.importer.formats.csv_format import detect_encoding

    text = "ID;Größe\n1;Café\n"
    assert detect_encoding(text.encode("utf-8")) == "utf-8"
    assert detect_encoding(text.encode("utf-8-sig")) == "utf-8"
    assert detect_encoding(text.encode("cp1252")) == "windows-1252"
    # 0x81 is undefined in Windows-1252, ISO-8859-1 still reads it
    assert detect_encoding(b"a;b\n\x81;\xfc\n") == "iso-8859-1"


def test_forced_encoding_overrides_detection() -> None:
    content = "ID;Größe\n1;Café\n".encode("cp1252")
    assert list(CsvFormat("windows-1252").parse(content)) == [{"ID": "1", "Größe": "Café"}]
    # Forcing UTF-8 on Windows-1252 bytes loses them as U+FFFD instead of raising
    row = list(CsvFormat("utf-8").parse(content))[0]
    assert any("\ufffd" in text for text in (*row.keys(), *row.values()))


def test_dry_run_warns_about_replacement_characters() -> None:
    from katalon.services.importer_service import dry_run

    result = dry_run([{"Titel": "Caf\ufffd"}, {"Titel": "ok"}], {"Titel": {"target": "label"}})
    assert any("Ersatzzeichen" in w["message"] and w["message"].startswith("1 Zellen") for w in result["warnings"])
    clean = dry_run([{"Titel": "ok"}], {"Titel": {"target": "label"}})
    assert not any("Ersatzzeichen" in w["message"] for w in clean["warnings"])
