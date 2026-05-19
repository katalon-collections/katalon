"""Import service module with backwards-compatible wrapper functions."""

from .formats import SourceFormat, SourceRecord, Selector, get_format_for
from .formats.csv_format import CsvFormat
from .formats.excel_format import ExcelFormat


def _parse_with_headers(fmt: SourceFormat, content: bytes) -> tuple[list[str], list[dict[str, str]]]:
    selectors = fmt.list_selectors(content)
    rows = list(fmt.parse(content))
    headers = [s.path for s in selectors]
    if not headers and rows:
        headers = list(rows[0].keys())
    return headers, rows


def parse_csv(content: bytes) -> tuple[list[str], list[dict[str, str]]]:
    """Parse CSV content (backwards-compatible wrapper).

    Returns:
        (headers, rows) tuple as before
    """
    return _parse_with_headers(CsvFormat(), content)


def parse_excel(content: bytes) -> tuple[list[str], list[dict[str, str]]]:
    """Parse Excel content (backwards-compatible wrapper).

    Returns:
        (headers, rows) tuple as before
    """
    return _parse_with_headers(ExcelFormat(), content)


def parse_file(filename: str, content: bytes) -> tuple[list[str], list[dict[str, str]], SourceFormat]:
    """Parse content using the format registry.

    Returns:
        (headers, rows, format) tuple.
    """
    fmt = get_format_for(filename, content)
    headers, rows = _parse_with_headers(fmt, content)
    return headers, rows, fmt


__all__ = [
    "parse_csv",
    "parse_excel",
    "parse_file",
    "get_format_for",
    "SourceFormat",
    "SourceRecord",
    "Selector",
]
