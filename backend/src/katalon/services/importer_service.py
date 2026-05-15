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


def parse_excel(content: bytes) -> tuple[list[str], list[dict[str, str]]]:
    import openpyxl  # lazy import — optional dependency

    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    header_row = next(rows_iter, None)
    if not header_row:
        return [], []
    headers = [str(c) if c is not None else "" for c in header_row]
    rows: list[dict[str, str]] = []
    for row in rows_iter:
        rows.append({
            headers[i]: str(v) if v is not None else ""
            for i, v in enumerate(row)
            if i < len(headers)
        })
    wb.close()
    return headers, rows


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
    field_defs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mapped = apply_mapping(rows, mapping)
    mapped_fields = set(mapping.values())
    required_fields = (
        {name for name, fd in field_defs.items() if fd.is_required}
        if field_defs
        else set()
    )
    missing_required = required_fields - mapped_fields

    errors: list[dict] = []
    warnings: list[dict] = []

    if missing_required:
        warnings.append({
            "row": None,
            "message": f"Pflichtfelder nicht gemappt: {', '.join(sorted(missing_required))}",
        })

    for i, rec in enumerate(mapped):
        row_num = i + 2  # 1-indexed + header row
        if not rec:
            errors.append({"row": row_num, "message": "Keine Felder gemappt — Zeile wird übersprungen"})
            continue
        for fname in required_fields:
            if fname in mapped_fields and not rec.get(fname):
                errors.append({"row": row_num, "message": f"Pflichtfeld '{fname}' ist leer"})

    return {
        "total": len(rows),
        "valid": len(rows) - len(errors),
        "errors": errors,
        "warnings": warnings,
        "preview": mapped[:5],
    }
