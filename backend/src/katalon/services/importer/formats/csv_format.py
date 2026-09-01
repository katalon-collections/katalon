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


class CsvFormat(SourceFormat):
    """CSV file format handler."""

    def sniff(self, content: bytes, filename: str) -> bool:
        """Match .csv or .tsv files."""
        lower = filename.lower()
        return lower.endswith(".csv") or lower.endswith(".tsv")

    def parse(self, content: bytes) -> Iterator[SourceRecord]:
        """Parse CSV and yield rows as dicts."""
        text = content.decode("utf-8-sig", errors="replace")
        delimiter = _detect_delimiter(text)
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        for row in reader:
            if reader.fieldnames:
                yield {k: (v if v is not None else "") for k, v in row.items()}

    def list_selectors(self, content: bytes) -> list[Selector]:
        """List headers as selectors."""
        text = content.decode("utf-8-sig", errors="replace")
        delimiter = _detect_delimiter(text)
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        if not reader.fieldnames:
            return []
        return [
            Selector(path=h, label=h, sample="", kind="scalar")
            for h in reader.fieldnames
        ]
