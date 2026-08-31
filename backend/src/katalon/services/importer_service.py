from __future__ import annotations

import re
from typing import Any

from jinja2.sandbox import SandboxedEnvironment
from rapidfuzz.distance import Levenshtein

from katalon.services.importer import parse_csv, parse_excel  # noqa: F401
from katalon.services.importer.formats.csv_format import (
    _detect_delimiter as detect_delimiter,  # noqa: F401
)

_JINJA_ENV = SandboxedEnvironment()


def _is_iso_date(val: str) -> bool:
    """Check if value looks like an ISO date (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS); BCE years with leading '-' (e.g. -0043-01-01)."""
    return bool(re.fullmatch(r"-?\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2})?", val.strip()))


def _is_number(val: str) -> bool:
    """Check if value is numeric (int or float)."""
    try:
        float(val.strip().replace(",", "."))
        return True
    except ValueError:
        return False


def _is_boolean(val: str) -> bool:
    return val.strip().lower() in {"true", "false", "1", "0", "ja", "nein", "yes", "no"}


def _row_values(row: dict[str, Any], selector: str) -> list[str]:
    """Normalize a selector's raw value to a list of non-empty strings.

    XML selectors that repeat within a record come back as a list from
    XmlFormat.parse(); CSV/Excel selectors and non-repeated XML paths are
    plain strings. This flattens both to a uniform list.
    """
    val = row.get(selector, "")
    if isinstance(val, list):
        return [str(v).strip() for v in val if str(v).strip()]
    s = str(val).strip()
    return [s] if s else []


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
    """Evaluate a Jinja2 template expression with `value` as context variable.

    Examples:
      {{ value }}                  -> raw value
      {{ value | upper }}          -> uppercase
      {{ value | trim }}           -> strip whitespace
      {{ value | replace('a','b')}} -> replace substring
      PREFIX_{{ value }}_SUFFIX    -> wrap with literal text

    Legacy ${value} syntax is converted automatically for backwards compatibility.
    """
    if not expression:
        return value
    # Backward compat: convert old ${value} markers to {{ value }}
    compat = re.sub(r"\$\{value(?::[^}]+)?\}", "{{ value }}", expression)
    try:
        return _JINJA_ENV.from_string(compat).render(value=value)
    except Exception:
        return value


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
                if not delim:
                    new_values.append(v)
                    continue
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


def _combine_row_values(row: dict[str, Any], transform: dict[str, Any]) -> str:
    sources = transform.get("sources", [])
    values = [_row_values(row, source)[0] if _row_values(row, source) else "" for source in sources]
    template = transform.get("template")
    if template:
        return re.sub(r"\{(\d+)\}", lambda match: values[int(match.group(1))] if int(match.group(1)) < len(values) else "", template)
    return str(transform.get("separator", " ")).join(value for value in values if value)


def apply_mapping(
    rows: list[dict[str, str]],
    mapping: dict[str, str] | dict[str, Any],
    field_defs: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[str | None]]:
    """Apply a source→field mapping to a list of source records.

    mapping: { selector -> field_name }
             OR { selector -> {"target": field_name, "transforms": [...]} }

    The selector is the dict key used to look up the value in each source record.
    For CSV/Excel that is the column header; for XML it is the Clark-notation tag
    path produced by XmlFormat.parse_flat().

    Returns:
      - list of metadata dicts ready for record creation
      - list of idno values (one per row, or None)

    Special field name '__idno__' maps to the record's idno column, not metadata.

    If field_defs is provided, values are coerced according to field_type:
    - number: parse to float/int
    - boolean: normalize to True/False
    """
    result: list[dict[str, Any]] = []
    idnos: list[str | None] = []

    # Normalize mapping to always have target + transforms
    normalized: dict[str, tuple[str, list[dict[str, Any]]]] = {}
    for selector, val in mapping.items():
        if isinstance(val, dict):
            normalized[selector] = (val.get("target", ""), val.get("transforms", []))
        else:
            normalized[selector] = (val, [])

    container_targets: dict[str, tuple[str, str]] = {}
    if field_defs:
        groups = {field.id: field.name for field in field_defs.values() if field.field_type == "group"}
        for field in field_defs.values():
            parent_name = groups.get(getattr(field, "parent_id", None))
            if parent_name:
                container_targets[f"{parent_name}.{field.name}"] = (parent_name, field.name)

    for row in rows:
        record: dict[str, Any] = {}
        containers: dict[str, dict[str, list[str]]] = {}
        row_idno: str | None = None
        for selector, (field_name, transforms) in normalized.items():
            combine = next((t for t in transforms if t.get("type") == "combine"), None)
            if combine:
                raws = [_combine_row_values(row, combine)]
                transforms = [t for t in transforms if t.get("type") != "combine"]
            else:
                raws = _row_values(row, selector)
            if not raws:
                continue

            # Special handling for idno
            if field_name == "__idno__":
                row_idno = raws[0]
                continue

            fd = field_defs.get(field_name) if field_defs else None
            container_target = container_targets.get(field_name)
            if container_target:
                group_name, child_name = container_target
                container_parts = [part for raw in raws for part in (apply_transforms(raw, transforms) if transforms else [raw])]
                containers.setdefault(group_name, {})[child_name] = container_parts
                continue
            field_type = fd.field_type if fd else "text"
            is_repeatable = fd.is_repeatable if fd else False

            # Apply transforms pipeline to every occurrence (repeated XML paths
            # yield multiple raw values), flattening the results.
            parts: list[str] = []
            for raw in raws:
                parts.extend(apply_transforms(raw, transforms) if transforms else [raw])

            # Repeatable fields: store as plain list of strings (form reads string[])
            if is_repeatable:
                if field_type == "url":
                    record[field_name] = [{"value": part, "label": ""} for part in parts]
                else:
                    record[field_name] = parts
                continue

            # For non-repeatable fields, store single plain value (form reads string/number/bool)
            single = parts[0] if parts else ""

            if field_type == "number":
                try:
                    num = float(single.replace(",", "."))
                    record[field_name] = int(num) if num == int(num) else num
                except ValueError:
                    record[field_name] = single
            elif field_type == "boolean":
                record[field_name] = single.lower() in {"true", "1", "ja", "yes"}
            elif field_type == "url":
                record[field_name] = {"value": single, "label": ""}
            else:
                record[field_name] = single
        for group_name, group_values in containers.items():
            count = max(len(parts) for parts in group_values.values())
            record[group_name] = [
                {child_name: parts[index] if index < len(parts) else "" for child_name, parts in group_values.items()}
                for index in range(count)
            ]
        result.append(record)
        idnos.append(row_idno)
    return result, idnos


def _validate_types(
    rows: list[dict[str, str]],
    mapping: dict[str, str] | dict[str, Any],
    field_defs: dict[str, Any],
) -> list[dict[str, Any]]:
    """Check field type constraints for all rows. Returns warning dicts (one per failing field).

    Collects up to 3 example failures per field for the warning message, but counts
    all mismatches for the total so the number is accurate.
    """
    # Build reverse mapping: field_name -> selector (first match wins)
    field_to_selector: dict[str, str] = {}
    for selector, v in mapping.items():
        fname = v.get("target", "") if isinstance(v, dict) else v
        if fname and fname != "__idno__" and fname not in field_to_selector:
            field_to_selector[fname] = selector

    examples: dict[str, list[tuple[int, str]]] = {}
    counts: dict[str, int] = {}

    for i, row in enumerate(rows):
        row_num = i + 2
        for fname, selector in field_to_selector.items():
            fd = field_defs.get(fname)
            if not fd:
                continue
            for raw in _row_values(row, selector):
                issue: str | None = None
                if fd.field_type == "number":
                    try:
                        float(raw.replace(",", "."))
                    except ValueError:
                        issue = f"'{raw[:30]}' ist keine gültige Zahl"
                elif fd.field_type == "date":
                    if not _is_iso_date(raw):
                        issue = f"'{raw[:30]}' sieht nicht wie ein ISO-Datum aus (YYYY-MM-DD, für v. Chr. mit - z.B. -0043-01-01)"
                elif fd.field_type == "boolean":
                    if not _is_boolean(raw):
                        issue = f"'{raw[:30]}' ist kein gültiger Boolean"
                elif fd.field_type == "url":
                    if not raw.lower().startswith(("http://", "https://")):
                        issue = f"'{raw[:30]}' ist keine vollständige http(s)-URL"

                if issue:
                    counts[fname] = counts.get(fname, 0) + 1
                    if fname not in examples:
                        examples[fname] = []
                    if len(examples[fname]) < 3:
                        examples[fname].append((row_num, issue))

    warnings: list[dict[str, Any]] = []
    for fname, ex in examples.items():
        fd = field_defs.get(fname)
        label = fd.label.get("de", fname) if fd and fd.label else fname
        sample = "; ".join(f"Zeile {r}: {m}" for r, m in ex)
        warnings.append({
            "row": None,
            "message": f"Feld '{label}': {counts[fname]} Typ-Fehler. Beispiele: {sample}",
        })
    return warnings


def _collect_vocab_values(
    rows: list[dict[str, str]],
    mapping: dict[str, str] | dict[str, Any],
    field_defs: dict[str, Any],
) -> dict[str, dict[str, int]]:
    """Return raw values (after splits) with occurrence counts per vocab-typed mapped field."""
    result: dict[str, dict[str, int]] = {}
    for selector, val in mapping.items():
        if isinstance(val, dict):
            field_name = val.get("target", "")
            transforms = val.get("transforms", [])
        else:
            field_name, transforms = val, []
        if not field_name or field_name == "__idno__":
            continue
        fd = field_defs.get(field_name)
        if not fd or fd.field_type not in ("vocab",):
            continue
        counts: dict[str, int] = {}
        for row in rows:
            for raw in _row_values(row, selector):
                parts = apply_transforms(raw, transforms) if transforms else [raw]
                for p in parts:
                    if p:
                        counts[p] = counts.get(p, 0) + 1
        result[field_name] = counts
    return result


CLUSTER_SIMILARITY_THRESHOLD = 0.82
CLUSTER_MAX_SIZE = 10


def _cluster_values(
    value_counts: dict[str, int],
    threshold: float = CLUSTER_SIMILARITY_THRESHOLD,
    max_cluster_size: int = CLUSTER_MAX_SIZE,
) -> list[dict[str, Any]]:
    """Group near-duplicate values (typos, case/whitespace variants) by normalized Levenshtein similarity.

    Greedy: most frequent unassigned value becomes a cluster's canonical suggestion; nearby
    values (by similarity of trimmed/lowercased form) join it, capped at max_cluster_size.
    Singleton clusters are dropped — only real variant groups are returned.
    """
    remaining = sorted(value_counts, key=lambda v: (-value_counts[v], v))
    assigned: set[str] = set()
    clusters: list[dict[str, Any]] = []
    for pivot in remaining:
        if pivot in assigned:
            continue
        variants = [pivot]
        assigned.add(pivot)
        pivot_norm = pivot.strip().lower()
        for candidate in remaining:
            if candidate in assigned or len(variants) >= max_cluster_size:
                continue
            cand_norm = candidate.strip().lower()
            if Levenshtein.normalized_similarity(pivot_norm, cand_norm) >= threshold:
                variants.append(candidate)
                assigned.add(candidate)
        if len(variants) > 1:
            clusters.append({
                "canonical": pivot,
                "variants": variants,
                "counts": {v: value_counts[v] for v in variants},
            })
    return clusters


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

    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if missing_required:
        warnings.append({
            "row": None,
            "message": f"Pflichtfelder nicht gemappt: {', '.join(sorted(missing_required))}",
        })

    if field_defs:
        groups = {field.id: field.name for field in field_defs.values() if field.field_type == "group"}
        targets = {
            target: groups.get(getattr(field, "parent_id", None))
            for field in field_defs.values()
            if groups.get(getattr(field, "parent_id", None))
            for target in [f"{groups[field.parent_id]}.{field.name}"]
        }
        for index, row in enumerate(rows):
            group_counts: dict[str, list[int]] = {}
            for selector, value in mapping.items():
                target = value.get("target", "") if isinstance(value, dict) else value
                group_name = targets.get(target)
                if group_name:
                    group_counts.setdefault(group_name, []).append(len(_row_values(row, selector)))
            for group_name, lengths in group_counts.items():
                if len(lengths) > 1 and len(set(lengths)) > 1:
                    errors.append({"row": index + 2, "message": f"Container '{group_name}': Subfelder haben unterschiedlich viele Wiederholungen"})

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
        for selector, val in mapping.items():
            field_name = val.get("target", "") if isinstance(val, dict) else val
            if field_name == "__idno__":
                continue
            if field_name in required_fields:
                continue
            if not _row_values(rows[i], selector):
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

    if field_defs:
        warnings.extend(_validate_types(rows, mapping, field_defs))

    vocab_value_counts: dict[str, dict[str, int]] = {}
    if field_defs:
        vocab_value_counts = _collect_vocab_values(rows, mapping, field_defs)

    vocab_clusters: dict[str, list[dict[str, Any]]] = {}
    for field_name, value_counts in vocab_value_counts.items():
        clusters = _cluster_values(value_counts)
        if clusters:
            vocab_clusters[field_name] = clusters

    return {
        "total": len(rows),
        "valid": len(rows) - len(errors),
        "errors": errors,
        "warnings": warnings,
        "preview": mapped[:5],
        "has_idno_mapping": has_idno_mapping,
        "vocab_stats": {name: sorted(counts) for name, counts in vocab_value_counts.items()},
        "vocab_clusters": vocab_clusters,
    }


def suggest_field_types(headers: list[str], rows: list[dict[str, str]]) -> dict[str, str]:
    """Return a map of column name -> suggested field_type for each column."""
    suggestions: dict[str, str] = {}
    for col in headers:
        values = [v for row in rows[:50] for v in _row_values(row, col)]  # sample first 50 rows
        suggestions[col] = _guess_field_type(values)
    return suggestions
