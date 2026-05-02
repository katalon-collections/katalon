from __future__ import annotations

import csv
import io
from typing import Any


def detect_delimiter(content: str) -> str:
    sample = content[:4096]
    sniffer = csv.Sniffer()
    try:
        dialect = sniffer.sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        return ","


def parse_csv(content: bytes) -> tuple[list[str], list[dict[str, str]]]:
    text = content.decode("utf-8-sig", errors="replace")
    delimiter = detect_delimiter(text)
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    headers = reader.fieldnames or []
    rows = [dict(row) for row in reader]
    return list(headers), rows


def apply_mapping(
    rows: list[dict[str, str]],
    mapping: dict[str, str],
) -> list[dict[str, Any]]:
    """
    mapping: { csv_column -> field_name }
    Returns list of metadata dicts ready for record creation.
    """
    result = []
    for row in rows:
        record: dict[str, Any] = {}
        for csv_col, field_name in mapping.items():
            val = row.get(csv_col, "").strip()
            if val:
                record[field_name] = [{"value": val}]
        result.append(record)
    return result


def dry_run(
    rows: list[dict[str, str]],
    mapping: dict[str, str],
) -> dict[str, Any]:
    mapped = apply_mapping(rows, mapping)
    errors: list[dict] = []
    for i, rec in enumerate(mapped):
        if not rec:
            errors.append({"row": i + 1, "error": "Keine gemappten Felder"})
    return {
        "total": len(rows),
        "valid": len(rows) - len(errors),
        "errors": errors,
        "preview": mapped[:5],
    }
