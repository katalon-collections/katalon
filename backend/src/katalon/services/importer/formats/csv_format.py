# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import csv
import io
from collections.abc import Iterator

from .base import Selector, SourceFormat, SourceRecord


def _detect_delimiter(content: str) -> str:
    """Detect CSV delimiter (,;tab|) using csv.Sniffer."""
    sample = content[:4096]
    sniffer = csv.Sniffer()
    try:
        dialect = sniffer.sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        return ","


ENCODINGS = ("utf-8", "windows-1252", "iso-8859-1")
_PYTHON_CODECS = {"utf-8": "utf-8-sig", "windows-1252": "cp1252", "iso-8859-1": "latin-1"}


def detect_encoding(content: bytes) -> str:
    """UTF-8 (with or without BOM) if the bytes are valid, else Windows-1252, else ISO-8859-1."""
    for name in ENCODINGS:
        try:
            content.decode(_PYTHON_CODECS[name])
        except UnicodeDecodeError:
            continue
        return name
    return "iso-8859-1"


def _decode(content: bytes, encoding: str | None = None) -> str:
    """Decode with the chosen encoding, or the detected one. A forced encoding the bytes do
    not fit keeps working: undecodable bytes become U+FFFD, which the dry run reports."""
    name = encoding if encoding in ENCODINGS else detect_encoding(content)
    return content.decode(_PYTHON_CODECS[name], errors="replace")


class CsvFormat(SourceFormat):
    """CSV file format handler. ``encoding`` forces one of ``ENCODINGS`` instead of detecting."""

    def __init__(self, encoding: str | None = None) -> None:
        self.encoding = encoding

    def sniff(self, content: bytes, filename: str) -> bool:
        """Match .csv or .tsv files."""
        lower = filename.lower()
        return lower.endswith(".csv") or lower.endswith(".tsv")

    def parse(self, content: bytes) -> Iterator[SourceRecord]:
        """Parse CSV and yield rows as dicts."""
        text = _decode(content, self.encoding)
        delimiter = _detect_delimiter(text)
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        for row in reader:
            if reader.fieldnames:
                yield {k: (v if v is not None else "") for k, v in row.items()}

    def list_selectors(self, content: bytes) -> list[Selector]:
        """List headers as selectors."""
        text = _decode(content, self.encoding)
        delimiter = _detect_delimiter(text)
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        if not reader.fieldnames:
            return []
        return [
            Selector(path=h, label=h, sample="", kind="scalar")
            for h in reader.fieldnames
        ]
