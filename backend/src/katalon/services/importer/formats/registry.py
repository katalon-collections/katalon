# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from .base import SourceFormat
from .csv_format import CsvFormat
from .excel_format import ExcelFormat
from .xml_format import XmlFormat

_FORMATS: list[SourceFormat] = [
    ExcelFormat(),  # More specific (checks magic bytes), check first
    CsvFormat(),
    XmlFormat(),  # Stub, lower priority
]


def get_format_for(filename: str, content: bytes) -> SourceFormat:
    """Get the appropriate format handler for a file.

    Args:
        filename: The uploaded filename
        content: File content as bytes

    Returns:
        A SourceFormat instance that can handle the file

    Raises:
        ValueError: If no format matches the file
    """
    for fmt in _FORMATS:
        if fmt.sniff(content, filename):
            return fmt
    raise ValueError(f"Unsupported file format: {filename}")
