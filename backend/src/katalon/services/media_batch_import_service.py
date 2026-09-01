# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import csv
import io
import re
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_UUID_PREFIX_RE = re.compile(
    r"^(?P<id>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})(?:[_\-\s\.].*)?$"
)


@dataclass(slots=True)
class MappingRow:
    row: int
    filename: str
    object_id: str
    media_type: str | None


def detect_delimiter(content: str) -> str:
    sample = content[:4096]
    sniffer = csv.Sniffer()
    try:
        dialect = sniffer.sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        return ","


def parse_mapping_csv(content: bytes) -> tuple[list[MappingRow], list[dict[str, str | int | None]]]:
    text = content.decode("utf-8-sig", errors="replace")
    delimiter = detect_delimiter(text)
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    headers = {h.lower().strip(): h for h in (reader.fieldnames or []) if h}

    filename_col = headers.get("filename") or headers.get("file") or headers.get("dateiname")
    object_id_col = headers.get("object_id") or headers.get("object") or headers.get("objekt_id") or headers.get("id")
    media_type_col = headers.get("media_type") or headers.get("medientyp")

    if not filename_col or not object_id_col:
        return [], [{
            "row": None,
            "message": "CSV benötigt Spalten für filename/dateiname und object_id/objekt_id",
        }]

    rows: list[MappingRow] = []
    errors: list[dict[str, str | int | None]] = []
    for i, row in enumerate(reader, start=2):
        filename = (row.get(filename_col) or "").strip()
        object_id = (row.get(object_id_col) or "").strip()
        media_type = (row.get(media_type_col) or "").strip() if media_type_col else ""
        if not filename:
            errors.append({"row": i, "message": "Dateiname fehlt"})
            continue
        if not object_id:
            errors.append({"row": i, "message": "Objekt-ID fehlt"})
            continue
        rows.append(MappingRow(row=i, filename=filename, object_id=object_id, media_type=media_type or None))
    return rows, errors


def normalize_filename(value: str) -> str:
    return unicodedata.normalize("NFC", Path(value).name).casefold()


def media_references_for_rows(
    rows: list[dict[str, object]], selector: str
) -> tuple[list[list[tuple[str, str]]], dict[str, Any]]:
    """Extract and validate pending media filenames from one import selector."""
    extracted: list[list[tuple[str, str]]] = []
    rows_by_name: dict[str, set[int]] = {}

    for row_index, row in enumerate(rows):
        raw = row.get(selector, "")
        values = raw if isinstance(raw, list) else [raw]
        references: list[tuple[str, str]] = []
        seen: set[str] = set()
        for value in values:
            if value is None:
                continue
            filename = Path(str(value).strip()).name
            normalized = normalize_filename(filename)
            if not filename or not normalized or normalized in seen:
                continue
            seen.add(normalized)
            references.append((filename, normalized))
            rows_by_name.setdefault(normalized, set()).add(row_index)
        extracted.append(references)

    conflicts = [
        {"filename": normalized, "rows": [row + 2 for row in sorted(row_indexes)]}
        for normalized, row_indexes in rows_by_name.items()
        if len(row_indexes) > 1
    ]
    return extracted, {
        "selector_found": any(selector in row for row in rows),
        "objects": sum(bool(references) for references in extracted),
        "files": sum(len(references) for references in extracted),
        "empty": sum(not references for references in extracted),
        "conflicts": conflicts,
    }


def folder_or_filename_object_id(relative_path: str) -> str | None:
    path = Path(relative_path)
    parent = path.parent.name
    if parent:
        try:
            return str(uuid.UUID(parent))
        except ValueError:
            pass

    match = _UUID_PREFIX_RE.match(path.name)
    if not match:
        return None
    try:
        return str(uuid.UUID(match.group("id")))
    except ValueError:
        return None
