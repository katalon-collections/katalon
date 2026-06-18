from __future__ import annotations

import csv
import io
import json
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import VocabularyTerm

DEFAULT_LABEL_LANGUAGE = "de"


@dataclass
class ImportTerm:
    term: str
    label: dict[str, str]
    inverse_label: dict[str, str]
    parent_term: str | None
    external_id: str | None
    row: int | None


def _norm(value: str | None) -> str:
    return (value or "").strip()


def _parse_mapping(mapping_raw: str | None) -> dict[str, str]:
    if not mapping_raw:
        return {}
    payload = json.loads(mapping_raw)
    if not isinstance(payload, dict):
        raise ValueError("Mapping muss ein JSON-Objekt sein")
    parsed: dict[str, str] = {}
    for key, value in payload.items():
        if isinstance(key, str) and isinstance(value, str):
            parsed[key] = value
    return parsed


def parse_mapping(mapping_raw: str | None) -> dict[str, str]:
    try:
        return _parse_mapping(mapping_raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Mapping ist kein gültiges JSON") from exc


def _merge_term(
    target: dict[str, ImportTerm],
    item: ImportTerm,
    errors: list[dict[str, Any]],
) -> None:
    existing = target.get(item.term)
    if existing is None:
        target[item.term] = item
        return
    existing.label.update(item.label)
    if item.inverse_label:
        existing.inverse_label.update(item.inverse_label)
    if item.external_id:
        existing.external_id = item.external_id
    if item.parent_term and not existing.parent_term:
        existing.parent_term = item.parent_term
    if item.parent_term and existing.parent_term and item.parent_term != existing.parent_term:
        errors.append({"row": item.row, "message": f"Konflikt bei parent_term für '{item.term}'"})


def _detect_delimiter(text: str) -> str:
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        return ","


def _decode_csv(content: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return content.decode(enc, errors="strict")
        except (UnicodeDecodeError, ValueError):
            continue
    return content.decode("utf-8-sig", errors="replace")


def parse_csv_terms(
    content: bytes,
    mapping: dict[str, str],
) -> tuple[list[ImportTerm], list[dict[str, Any]]]:
    text = _decode_csv(content)
    reader = csv.DictReader(io.StringIO(text), delimiter=_detect_delimiter(text))
    terms: dict[str, ImportTerm] = {}
    errors: list[dict[str, Any]] = []

    for i, row in enumerate(reader, start=2):
        row_values = {_norm(k): _norm(v) for k, v in row.items() if k}
        term = ""
        parent_term = None
        external_id = None
        label: dict[str, str] = {}
        inverse_label: dict[str, str] = {}

        for source_col, target_field in mapping.items():
            source_val = row_values.get(source_col, "")
            if not source_val:
                continue
            if target_field == "term":
                term = source_val
            elif target_field == "parent_term":
                parent_term = source_val
            elif target_field == "external_id":
                external_id = source_val
            elif target_field.startswith("label:"):
                lang = target_field.split(":", 1)[1].strip()
                if lang:
                    label[lang] = source_val
            elif target_field.startswith("inverse_label:"):
                lang = target_field.split(":", 1)[1].strip()
                if lang:
                    inverse_label[lang] = source_val

        if not term:
            errors.append({"row": i, "message": "Pflichtfeld 'term' fehlt oder ist leer"})
            continue

        _merge_term(
            terms,
            ImportTerm(
                term=term,
                label=label,
                inverse_label=inverse_label,
                parent_term=parent_term,
                external_id=external_id,
                row=i,
            ),
            errors,
        )

    return list(terms.values()), errors


def parse_json_terms(content: bytes) -> tuple[list[ImportTerm], list[dict[str, Any]]]:
    try:
        payload = json.loads(_decode_csv(content))
    except json.JSONDecodeError as exc:
        return [], [{"row": None, "message": f"Ungültiges JSON: {exc.msg}"}]

    if isinstance(payload, dict):
        raw_items = payload.get("terms")
    else:
        raw_items = payload

    if not isinstance(raw_items, list):
        return [], [
            {"row": None, "message": "JSON muss eine Liste oder {'terms': [...]} enthalten"}
        ]

    terms: dict[str, ImportTerm] = {}
    errors: list[dict[str, Any]] = []

    def parse_term_node(node: Any, parent_term: str | None) -> None:
        if not isinstance(node, dict):
            errors.append({"row": None, "message": "Eintrag ist kein Objekt"})
            return
        term = _norm(str(node.get("term", "")))
        if not term:
            errors.append({"row": None, "message": "Pflichtfeld 'term' fehlt"})
            return

        raw_label = node.get("label", {})
        label: dict[str, str] = {}
        if isinstance(raw_label, dict):
            label = {str(k): _norm(str(v)) for k, v in raw_label.items() if _norm(str(v))}
        elif isinstance(raw_label, str) and _norm(raw_label):
            label = {DEFAULT_LABEL_LANGUAGE: _norm(raw_label)}

        this_parent = _norm(str(node.get("parent_term", ""))) or parent_term
        external_id = _norm(str(node.get("external_id", ""))) or None
        raw_inverse = node.get("inverse_label", {})
        inverse_label: dict[str, str] = {}
        if isinstance(raw_inverse, dict):
            inverse_label = {str(k): _norm(str(v)) for k, v in raw_inverse.items() if _norm(str(v))}
        elif isinstance(raw_inverse, str) and _norm(raw_inverse):
            inverse_label = {DEFAULT_LABEL_LANGUAGE: _norm(raw_inverse)}
        _merge_term(
            terms,
            ImportTerm(
                term=term,
                label=label,
                inverse_label=inverse_label,
                parent_term=this_parent,
                external_id=external_id,
                row=None,
            ),
            errors,
        )

        children = node.get("children", [])
        if children is None:
            children = []
        if not isinstance(children, list):
            errors.append({"row": None, "message": f"children für '{term}' muss eine Liste sein"})
            return
        for child in children:
            parse_term_node(child, term)

    for item in raw_items:
        parse_term_node(item, None)

    return list(terms.values()), errors


async def import_vocabulary_terms(
    db: AsyncSession,
    vocab_id: uuid.UUID,
    terms: list[ImportTerm],
    strategy: str,
    dry_run: bool,
) -> dict[str, Any]:
    result = await db.execute(
        select(VocabularyTerm).where(VocabularyTerm.vocabulary_id == vocab_id)
    )
    existing_terms = list(result.scalars().all())
    existing_by_term = {t.term: t for t in existing_terms}
    combined_term_names = set(existing_by_term) | {t.term for t in terms}

    errors: list[dict[str, Any]] = []
    valid_terms: list[ImportTerm] = []
    for item in terms:
        if item.parent_term and item.parent_term not in combined_term_names:
            errors.append(
                {
                    "row": item.row,
                    "message": f"Unbekannter parent_term '{item.parent_term}' für '{item.term}'",
                }
            )
            continue
        valid_terms.append(item)

    existing_terms_set = set(existing_by_term)
    imported_terms_set = {t.term for t in valid_terms}
    stats = {
        "total": len(terms),
        "created": 0,
        "updated": 0,
        "deleted": 0,
        "errors": errors,
    }

    if strategy == "replace":
        stats["deleted"] = len(existing_terms)
        stats["created"] = len(valid_terms)
    else:
        stats["created"] = len(imported_terms_set - existing_terms_set)
        stats["updated"] = len(imported_terms_set & existing_terms_set)

    if dry_run:
        return stats

    if strategy == "replace":
        for existing in existing_terms:
            await db.delete(existing)
        await db.flush()
        existing_by_term = {}

    touched: dict[str, VocabularyTerm] = {}
    for item in valid_terms:
        term_model = existing_by_term.get(item.term)
        if term_model is None:
            term_model = VocabularyTerm(
                vocabulary_id=vocab_id,
                term=item.term,
                label={},
                inverse_label={},
                parent_id=None,
            )
            db.add(term_model)
        if item.label:
            term_model.label = item.label
        if item.inverse_label:
            term_model.inverse_label = item.inverse_label
        touched[item.term] = term_model
    await db.flush()

    lookup = {**existing_by_term, **touched}
    for item in valid_terms:
        term_model = lookup[item.term]
        if item.parent_term:
            parent = lookup.get(item.parent_term)
            term_model.parent_id = parent.id if parent else None
        else:
            term_model.parent_id = None

    await db.flush()
    return stats
