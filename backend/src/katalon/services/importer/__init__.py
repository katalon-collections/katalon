"""Import service module with backwards-compatible wrapper functions."""

from .formats import SourceFormat, SourceRecord, Selector, get_format_for
from .formats.csv_format import CsvFormat
from .formats.excel_format import ExcelFormat


def parse_csv(content: bytes) -> tuple[list[str], list[dict[str, str]]]:
    """Parse CSV content (backwards-compatible wrapper).

    Returns:
        (headers, rows) tuple as before
    """
    fmt = CsvFormat()
    rows = list(fmt.parse(content))
    headers = list(rows[0].keys()) if rows else []
    return headers, rows


def parse_excel(content: bytes) -> tuple[list[str], list[dict[str, str]]]:
    """Parse Excel content (backwards-compatible wrapper).

    Returns:
        (headers, rows) tuple as before
    """
    fmt = ExcelFormat()
    rows = list(fmt.parse(content))
    headers = list(rows[0].keys()) if rows else []
    return headers, rows


__all__ = [
    "parse_csv",
    "parse_excel",
    "get_format_for",
    "SourceFormat",
    "SourceRecord",
    "Selector",
]
