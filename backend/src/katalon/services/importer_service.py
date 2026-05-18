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
) -> tuple[list[dict[str, Any]], list[str | None]]:
    """
    mapping: { csv_column -> field_name }
    Returns:
      - list of metadata dicts ready for record creation
      - list of idno values (one per row, or None)

    Special field name '__idno__' maps to the record's idno column, not metadata.

    If field_defs is provided, values are transformed according to field_type:
    - repeatable fields: split on ';' if the raw value contains it
    - number: parse to float/int
    - boolean: normalize to True/False
    """
    result: list[dict[str, Any]] = []
    idnos: list[str | None] = []
    for row in rows:
        record: dict[str, Any] = {}
        row_idno: str | None = None
        for csv_col, field_name in mapping.items():
            raw = row.get(csv_col, "").strip()
            if not raw:
                continue

            # Special handling for idno
            if field_name == "__idno__":
                row_idno = raw
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
        idnos.append(row_idno)
    return result, idnos


def dry_run(
    rows: list[dict[str, str]],
    mapping: dict[str, str],
    field_defs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mapped, idnos = apply_mapping(rows, mapping, field_defs)
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

    # Check for idno mapping
    has_idno_mapping = "__idno__" in mapped_fields
    if has_idno_mapping:
        empty_idnos = sum(1 for i, idno in enumerate(idnos) if not idno)
        if empty_idnos > 0:
            warnings.append({
                "row": None,
                "message": f"{empty_idnos} Zeilen haben keine ID-Nummer (leere idno-Spalte)",
            })

    # Collect empty-field stats per mapped field (exclude __idno__)
    empty_field_counts: dict[str, int] = {}
    for i, rec in enumerate(mapped):
        row_num = i + 2
        if not rec and not idnos[i]:
            errors.append({"row": row_num, "message": "Keine Felder gemappt — Zeile wird übersprungen"})
            continue
        for fname in required_fields:
            if fname in mapped_fields and not rec.get(fname):
                errors.append({"row": row_num, "message": f"Pflichtfeld '{fname}' ist leer"})

        # Track empty values for non-required mapped fields
        for csv_col, field_name in mapping.items():
            if field_name == "__idno__":
                continue
            if field_name in required_fields:
                continue
            raw = rows[i].get(csv_col, "").strip()
            if not raw:
                empty_field_counts[field_name] = empty_field_counts.get(field_name, 0) + 1

    # Aggregate empty-field warnings: only show if >10% of rows are empty
    total_rows = len(rows)
    for fname, count in empty_field_counts.items():
        pct = count / total_rows * 100
        if pct > 10:
            fd = field_defs.get(fname) if field_defs else None
            label = fd.label.get("de", fname) if fd and fd.label else fname
            warnings.append({
                "row": None,
                "message": f"Feld '{label}' ist in {count} von {total_rows} Zeilen ({pct:.0f}%) leer",
            })

    # Type validation: collect per-field, show first 3 examples
    type_issues: dict[str, list[tuple[int, str]]] = {}
    if field_defs:
        for i, rec in enumerate(mapped):
            row_num = i + 2
            for fname, val in rec.items():
                fd = field_defs.get(fname)
                if not fd:
                    continue
                raw_val = rows[i].get(
                    next((k for k, v in mapping.items() if v == fname), ""), ""
                ).strip()
                if not raw_val:
                    continue

                issue = None
                if fd.field_type == "number":
                    try:
                        float(raw_val.replace(",", "."))
                    except ValueError:
                        issue = f"'{raw_val[:30]}' ist keine gültige Zahl"
                elif fd.field_type == "date":
                    if not _is_iso_date(raw_val):
                        issue = f"'{raw_val[:30]}' sieht nicht wie ein ISO-Datum aus (YYYY-MM-DD)"
                elif fd.field_type == "boolean":
                    if not _is_boolean(raw_val):
                        issue = f"'{raw_val[:30]}' ist kein gültiger Boolean"

                if issue:
                    if fname not in type_issues:
                        type_issues[fname] = []
                    if len(type_issues[fname]) < 3:
                        type_issues[fname].append((row_num, issue))

    for fname, issues in type_issues.items():
        fd = field_defs.get(fname) if field_defs else None
        label = fd.label.get("de", fname) if fd and fd.label else fname
        total_issues = sum(
            1 for i, rec in enumerate(mapped)
            for fn in rec
            if fn == fname
            for csv_col, field_name in mapping.items()
            if field_name == fname and not rows[i].get(csv_col, "").strip()
        )
        # Count actual type mismatches
        mismatch_count = len(issues)
        for i, rec in enumerate(mapped):
            if fname not in rec:
                continue
            raw_val = rows[i].get(
                next((k for k, v in mapping.items() if v == fname), ""), ""
            ).strip()
            if not raw_val:
                continue
            fd = field_defs.get(fname)
            if not fd:
                continue
            is_bad = False
            if fd.field_type == "number":
                try:
                    float(raw_val.replace(",", "."))
                except ValueError:
                    is_bad = True
            elif fd.field_type == "date":
                if not _is_iso_date(raw_val):
                    is_bad = True
            elif fd.field_type == "boolean":
                if not _is_boolean(raw_val):
                    is_bad = True
            if is_bad:
                mismatch_count += 1

        if mismatch_count > 0:
            examples = "; ".join(f"Zeile {r}: {m}" for r, m in issues)
            warnings.append({
                "row": None,
                "message": f"Feld '{label}': {mismatch_count} Typ-Fehler. Beispiele: {examples}",
            })

    return {
        "total": len(rows),
        "valid": len(rows) - len(errors),
        "errors": errors,
        "warnings": warnings,
        "preview": mapped[:5],
        "has_idno_mapping": has_idno_mapping,
    }


def suggest_field_types(headers: list[str], rows: list[dict[str, str]]) -> dict[str, str]:
    """Return a map of column name -> suggested field_type for each column."""
    suggestions: dict[str, str] = {}
    for col in headers:
        values = [row.get(col, "") for row in rows[:50]]  # sample first 50 rows
        suggestions[col] = _guess_field_type(values)
    return suggestions
