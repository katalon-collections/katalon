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


def _eval_expression(expression: str, value: str) -> str:
    """Evaluate a simple template expression with ${value} and filters.

    Supported filters:
      ${value}           - raw value
      ${value:upper}     - uppercase
      ${value:lower}     - lowercase
      ${value:trim}      - strip whitespace
      ${value:slice(a,b)}- substring
      ${value:replace(x,y)} - replace substring
    """
    if not expression:
        return value

    result = expression
    # Match ${value} or ${value:filter} or ${value:filter(args)}
    pattern = re.compile(r"\$\{value(?::([^}]+))?\}")

    def _apply_filter(val: str, filt: str | None) -> str:
        if not filt:
            return val
        if filt == "upper":
            return val.upper()
        if filt == "lower":
            return val.lower()
        if filt == "trim":
            return val.strip()
        m = re.match(r"slice\((\d+)(?:,(\d+))?\)", filt)
        if m:
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else None
            return val[start:end]
        m = re.match(r"replace\(([^,]+),([^)]+)\)", filt)
        if m:
            return val.replace(m.group(1), m.group(2))
        return val

    for match in pattern.finditer(expression):
        full = match.group(0)
        filt = match.group(1)
        result = result.replace(full, _apply_filter(value, filt), 1)

    return result


def apply_transforms(value: str, transforms: list[dict[str, Any]]) -> list[str]:
    """Apply a chain of transforms to a single cell value.

    Returns a list of values (split may produce multiple).
    """
    values: list[str] = [value]
    for t in transforms:
        ttype = t.get("type", "")
        new_values: list[str] = []
        for v in values:
            if ttype == "split":
                delim = t.get("delimiter", ";")
                filter_empty = t.get("filter_empty", True)
                parts = [p.strip() for p in v.split(delim) if p.strip() or not filter_empty]
                new_values.extend(parts)
            elif ttype == "replace":
                search = t.get("search", "")
                replace = t.get("replace", "")
                case_sensitive = t.get("case_sensitive", True)
                flags = 0 if case_sensitive else re.IGNORECASE
                new_values.append(re.sub(re.escape(search), replace, v, flags=flags))
            elif ttype == "regex_extract":
                pattern = t.get("pattern", "")
                group = t.get("group", 0)
                try:
                    m = re.search(pattern, v)
                    new_values.append(m.group(group) if m else v)
                except re.error:
                    new_values.append(v)
            elif ttype == "trim":
                new_values.append(v.strip())
            elif ttype == "vocab_map":
                vocab_map = t.get("vocab_map", {})
                strict = t.get("strict", False)
                mapped = vocab_map.get(v.strip())
                if mapped is not None:
                    new_values.append(mapped)
                elif not strict:
                    new_values.append(v)
                # if strict and no mapping, drop the value
            elif ttype == "expression":
                expr = t.get("expression", "")
                new_values.append(_eval_expression(expr, v))
            else:
                new_values.append(v)
        filter_empty = t.get("filter_empty", True)
        values = [v for v in new_values if v.strip() or not filter_empty]
        if not values:
            break
    return values


def apply_mapping(
    rows: list[dict[str, str]],
    mapping: dict[str, str] | dict[str, Any],
    field_defs: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[str | None]]:
    """
    mapping: { csv_column -> field_name }  OR  { csv_column -> {"target": field_name, "transforms": [...]} }
    Returns:
      - list of metadata dicts ready for record creation
      - list of idno values (one per row, or None)

    Special field name '__idno__' maps to the record's idno column, not metadata.

    If field_defs is provided, values are transformed according to field_type:
    - number: parse to float/int
    - boolean: normalize to True/False
    """
    result: list[dict[str, Any]] = []
    idnos: list[str | None] = []

    # Normalize mapping to always have target + transforms
    normalized: dict[str, tuple[str, list[dict[str, Any]]]] = {}
    for csv_col, val in mapping.items():
        if isinstance(val, dict):
            normalized[csv_col] = (val.get("target", ""), val.get("transforms", []))
        else:
            normalized[csv_col] = (val, [])

    for row in rows:
        record: dict[str, Any] = {}
        row_idno: str | None = None
        for csv_col, (field_name, transforms) in normalized.items():
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

            # Apply transforms pipeline
            if transforms:
                parts = apply_transforms(raw, transforms)
            else:
                parts = [raw]

            # If result is multiple values AND field is repeatable, wrap as list
            if is_repeatable:
                record[field_name] = [{"value": p} for p in parts]
                continue

            # For non-repeatable fields, store single value (not a list)
            single = parts[0] if parts else ""

            # Type transformations
            if field_type == "number":
                try:
                    num = float(single.replace(",", "."))
                    record[field_name] = {"value": int(num) if num == int(num) else num}
                except ValueError:
                    record[field_name] = {"value": single}
            elif field_type == "boolean":
                record[field_name] = {"value": single.lower() in {"true", "1", "ja", "yes"}}
            elif field_type == "date":
                record[field_name] = {"value": single}
            else:
                record[field_name] = {"value": single}
        result.append(record)
        idnos.append(row_idno)
    return result, idnos


def dry_run(
    rows: list[dict[str, str]],
    mapping: dict[str, str] | dict[str, Any],
    field_defs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mapped, idnos = apply_mapping(rows, mapping, field_defs)

    # Extract mapped field names (handle both old and new mapping format)
    mapped_fields: set[str] = set()
    for v in mapping.values():
        if isinstance(v, dict):
            mapped_fields.add(v.get("target", ""))
        else:
            mapped_fields.add(v)

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
        for csv_col, val in mapping.items():
            field_name = val.get("target", "") if isinstance(val, dict) else val
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
                # Find the csv column that maps to this field
                raw_val = ""
                for csv_col, v in mapping.items():
                    mapped_name = v.get("target", "") if isinstance(v, dict) else v
                    if mapped_name == fname:
                        raw_val = rows[i].get(csv_col, "").strip()
                        break
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
        # Count actual type mismatches
        mismatch_count = len(issues)
        for i, rec in enumerate(mapped):
            if fname not in rec:
                continue
            raw_val = ""
            for csv_col, v in mapping.items():
                mapped_name = v.get("target", "") if isinstance(v, dict) else v
                if mapped_name == fname:
                    raw_val = rows[i].get(csv_col, "").strip()
                    break
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
