from __future__ import annotations

import csv
import io
import re
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


def _is_iso_date(val: str) -> bool:
    """Check if value looks like an ISO date (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)."""
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2})?", val.strip()))


def _is_number(val: str) -> bool:
    """Check if value is numeric (int or float)."""
    try:
        float(val.strip().replace(",", "."))
        return True
    except ValueError:
        return False


def _is_boolean(val: str) -> bool:
    return val.strip().lower() in {"true", "false", "1", "0", "ja", "nein", "yes", "no"}


def _guess_field_type(values: list[str]) -> str:
    """Heuristic to suggest a field type based on sample values."""
    non_empty = [v.strip() for v in values if v.strip()]
    if not non_empty:
        return "text"
    if all(_is_boolean(v) for v in non_empty):
        return "boolean"
    if all(_is_number(v) for v in non_empty):
        return "number"
    if all(_is_iso_date(v) for v in non_empty):
        return "date"
    return "text"


def apply_mapping(
    rows: list[dict[str, str]],
    mapping: dict[str, str],
    field_defs: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    mapping: { csv_column -> field_name }
    Returns list of metadata dicts ready for record creation.

    If field_defs is provided, values are transformed according to field_type:
    - repeatable fields: split on ';' if the raw value contains it
    - number: parse to float/int
    - boolean: normalize to True/False
    """
    result = []
    for row in rows:
        record: dict[str, Any] = {}
        for csv_col, field_name in mapping.items():
            raw = row.get(csv_col, "").strip()
            if not raw:
                continue

            fd = field_defs.get(field_name) if field_defs else None
            field_type = fd.field_type if fd else "text"
            is_repeatable = fd.is_repeatable if fd else False

            # Handle repeatable fields: split on ';' if value contains it
            if is_repeatable and ";" in raw:
                parts = [p.strip() for p in raw.split(";") if p.strip()]
                record[field_name] = [{"value": p} for p in parts]
                continue

            # Type transformations
            if field_type == "number":
                try:
                    num = float(raw.replace(",", "."))
                    record[field_name] = [{"value": int(num) if num == int(num) else num}]
                except ValueError:
                    record[field_name] = [{"value": raw}]
            elif field_type == "boolean":
                record[field_name] = [{"value": raw.lower() in {"true", "1", "ja", "yes"}}]
            elif field_type == "date":
                record[field_name] = [{"value": raw}]
            else:
                record[field_name] = [{"value": raw}]
        result.append(record)
    return result


def dry_run(
    rows: list[dict[str, str]],
    mapping: dict[str, str],
    field_defs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mapped = apply_mapping(rows, mapping, field_defs)
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

        # Type validation
        if field_defs:
            for fname, val in rec.items():
                fd = field_defs.get(fname)
                if not fd:
                    continue
                raw_val = rows[i].get(
                    next((k for k, v in mapping.items() if v == fname), ""), ""
                ).strip()
                if not raw_val:
                    continue

                if fd.field_type == "number":
                    try:
                        float(raw_val.replace(",", "."))
                    except ValueError:
                        warnings.append({
                            "row": row_num,
                            "message": f"Feld '{fname}': Wert '{raw_val[:30]}' ist keine gültige Zahl",
                        })
                elif fd.field_type == "date":
                    if not _is_iso_date(raw_val):
                        warnings.append({
                            "row": row_num,
                            "message": f"Feld '{fname}': Wert '{raw_val[:30]}' sieht nicht wie ein ISO-Datum aus (YYYY-MM-DD)",
                        })
                elif fd.field_type == "boolean":
                    if not _is_boolean(raw_val):
                        warnings.append({
                            "row": row_num,
                            "message": f"Feld '{fname}': Wert '{raw_val[:30]}' ist kein gültiger Boolean",
                        })

    return {
        "total": len(rows),
        "valid": len(rows) - len(errors),
        "errors": errors,
        "warnings": warnings,
        "preview": mapped[:5],
    }


def suggest_field_types(headers: list[str], rows: list[dict[str, str]]) -> dict[str, str]:
    """Return a map of column name -> suggested field_type for each column."""
    suggestions: dict[str, str] = {}
    for col in headers:
        values = [row.get(col, "") for row in rows[:50]]  # sample first 50 rows
        suggestions[col] = _guess_field_type(values)
    return suggestions
