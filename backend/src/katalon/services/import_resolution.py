# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Resolve plain import text into vocabulary terms and relation targets.

Shared by the dry-run endpoint and the import worker so both behave the same.
Missing vocabulary terms and relation targets are created through the session; the
dry-run wraps the call in a savepoint it rolls back, the worker commits.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import FieldDefinition, Vocabulary, VocabularyTerm
from katalon.services.importer_service import normalize_term_key

_TITLE_KEYS = ("label", "title", "titel", "name", "bezeichnung", "display_name", "place_name")


@dataclass
class ResolutionReport:
    """Outcome of a resolution pass. Row indexes are 0-based positions in ``records``."""

    row_errors: dict[int, list[str]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    new_terms: dict[str, set[str]] = field(default_factory=dict)
    unmatched: dict[str, set[str]] = field(default_factory=dict)
    created_records: list[tuple[str, Any]] = field(default_factory=list)

    def error(self, index: int, message: str) -> None:
        messages = self.row_errors.setdefault(index, [])
        if message not in messages:
            messages.append(message)


def _field_label(fd: Any) -> str:
    label = getattr(fd, "label", None) or {}
    return str(label.get("de") or label.get("en") or fd.name)


def _as_items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else [value]


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------


def _term_display_label(term: VocabularyTerm) -> str:
    labels = term.label or {}
    return str(labels.get("de") or labels.get("en") or term.term)


async def resolve_vocab_terms(
    session: AsyncSession,
    field_defs: dict[str, Any],
    records: list[dict[str, Any]],
    modes: Mapping[str, str] | None = None,
) -> ResolutionReport:
    """Replace plain strings in strict vocab fields with ``{id, label}`` entries.

    A value matches a term by its code or by any of its language labels (normalized:
    NFKC, whitespace, casefold). A label shared by several terms is ambiguous and
    reported per row. Without a match the term is created ("extend", default) or the
    value is dropped and reported ("match_only"), per field via ``modes``.
    """
    report = ResolutionReport()
    modes = modes or {}
    vocab_fields: dict[str, uuid.UUID] = {}
    for fname, fd in field_defs.items():
        if fd.field_type != "vocab":
            continue
        vid = (fd.settings or {}).get("vocabulary_id")
        if not vid:
            continue
        try:
            vocab_fields[fname] = uuid.UUID(str(vid))
        except ValueError:
            continue
    if not vocab_fields:
        return report

    by_code: dict[uuid.UUID, dict[str, dict[str, Any]]] = {}
    by_label: dict[uuid.UUID, dict[str, list[dict[str, Any]]]] = {}
    dropped: dict[str, dict[str, int]] = {}

    async def load(vocab_id: uuid.UUID) -> None:
        if vocab_id in by_code:
            return
        codes: dict[str, dict[str, Any]] = {}
        labels: dict[str, list[dict[str, Any]]] = {}
        rows = await session.execute(
            select(VocabularyTerm).where(VocabularyTerm.vocabulary_id == vocab_id)
        )
        for term in rows.scalars().all():
            entry = {"id": str(term.id), "label": _term_display_label(term)}
            codes[normalize_term_key(term.term)] = entry
            seen: set[str] = set()
            for text in (term.label or {}).values():
                if not isinstance(text, str) or not text.strip():
                    continue
                key = normalize_term_key(text)
                if key not in seen:
                    seen.add(key)
                    labels.setdefault(key, []).append(entry)
        by_code[vocab_id] = codes
        by_label[vocab_id] = labels

    async def find(index: int, fname: str, vocab_id: uuid.UUID, text: str) -> dict[str, Any] | None:
        await load(vocab_id)
        key = normalize_term_key(text)
        if key in by_code[vocab_id]:
            return by_code[vocab_id][key]
        candidates = by_label[vocab_id].get(key, [])
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            report.error(
                index, f"Feld '{_field_label(field_defs[fname])}': '{text.strip()}' ist mehrdeutig."
            )
            return None
        if modes.get(fname) == "match_only":
            counts = dropped.setdefault(fname, {})
            counts[text.strip()] = counts.get(text.strip(), 0) + 1
            report.unmatched.setdefault(fname, set()).add(normalize_term_key(text))
            return None
        if await session.get(Vocabulary, vocab_id) is None:
            return None
        clean = " ".join(text.split())
        term = VocabularyTerm(vocabulary_id=vocab_id, term=clean, label={"de": clean})
        session.add(term)
        await session.flush()
        entry = {"id": str(term.id), "label": term.term}
        by_code[vocab_id][key] = entry
        report.new_terms.setdefault(fname, set()).add(clean)
        return entry

    for index, record in enumerate(records):
        for fname, vocab_id in vocab_fields.items():
            value = record.get(fname)
            if value is None:
                continue
            if isinstance(value, dict):
                continue
            resolved = []
            for item in _as_items(value):
                if isinstance(item, str) and item.strip():
                    entry = await find(index, fname, vocab_id, item)
                    if entry:
                        resolved.append(entry)
                elif isinstance(item, dict):
                    resolved.append(item)
            if not resolved:
                record.pop(fname, None)
            elif isinstance(value, list):
                record[fname] = resolved
            else:
                record[fname] = resolved[0]

    for fname, counts in dropped.items():
        sample = ", ".join(sorted(counts)[:10])
        more = f" (+{len(counts) - 10} weitere)" if len(counts) > 10 else ""
        report.warnings.append(
            f"Feld '{_field_label(field_defs[fname])}': {sum(counts.values())} Werte ohne "
            f"passenden Term verworfen: {sample}{more}"
        )
    return report


# ---------------------------------------------------------------------------
# Relations
# ---------------------------------------------------------------------------


async def resolve_relations(
    session: AsyncSession,
    field_defs: dict[str, Any],
    records: list[dict[str, Any]],
    options: dict[str, dict[str, str]] | None = None,
    *,
    user_id: uuid.UUID | None = None,
) -> ResolutionReport:
    """Replace plain strings in top-level relation fields with ``{id, label, relation_type}``.

    ``options[field]`` holds ``lookup`` ("idno", default, or "label") and ``on_missing``
    ("error", default, or "create"). A label shared by several records is ambiguous and
    always an error. Created targets are drafts and returned in ``created_records`` so
    the caller can index them.
    """
    from katalon.services.relation_service import _RECORD_MODELS
    from katalon.services.search_service import _extract_title

    report = ResolutionReport()
    options = options or {}
    relation_fields = {
        name: fd
        for name, fd in field_defs.items()
        if fd.field_type == "relation"
        and getattr(fd, "parent_id", None) is None
        and (fd.settings or {}).get("target_type") in _RECORD_MODELS
    }
    if not relation_fields:
        return report

    # (field name) -> {lookup key -> [records]}; created targets are added too.
    index_cache: dict[str, dict[str, list[Any]]] = {}
    title_key_cache: dict[tuple[str, str | None], str] = {}

    def subtype_of(target_type: str, rec: Any) -> str | None:
        return getattr(rec, f"{target_type}_type", None)

    def usable(rec: Any) -> bool:
        return getattr(rec, "deleted_at", None) is None

    async def load_index(name: str, target_type: str, subtype: str | None, lookup: str,
                         wanted: set[str]) -> None:
        model = _RECORD_MODELS[target_type]
        cache = index_cache.setdefault(name, {})
        if lookup == "idno":
            missing = {v for v in wanted if v not in cache}
            if not missing:
                return
            rows = await session.execute(select(model).where(model.idno.in_(missing)))
            for rec in rows.scalars().all():
                if usable(rec) and (not subtype or subtype_of(target_type, rec) == subtype):
                    cache.setdefault(rec.idno, []).append(rec)
            for value in missing:
                cache.setdefault(value, [])
            return
        if cache.get("__loaded__") is not None:
            return
        cache["__loaded__"] = []
        rows = await session.execute(select(model))
        for rec in rows.scalars().all():
            if not usable(rec) or (subtype and subtype_of(target_type, rec) != subtype):
                continue
            title = _extract_title(rec.metadata_ or {}) or (rec.idno or "")
            if title:
                cache.setdefault(normalize_term_key(title), []).append(rec)

    async def title_key(target_type: str, subtype: str | None) -> str:
        key = (target_type, subtype)
        if key not in title_key_cache:
            names = set(
                (
                    await session.execute(
                        select(FieldDefinition.name).where(
                            FieldDefinition.target_type == target_type,
                            FieldDefinition.is_deleted.is_(False),
                            FieldDefinition.parent_id.is_(None),
                        )
                    )
                )
                .scalars()
                .all()
            )
            title_key_cache[key] = next((k for k in _TITLE_KEYS if k in names), "label")
        return title_key_cache[key]

    async def create_target(target_type: str, subtype: str | None, text: str) -> Any:
        from katalon.core.models import AdminConfig
        from katalon.services.audit_service import log_change
        from katalon.services.idno_service import consume_next_idno

        model = _RECORD_MODELS[target_type]
        kwargs: dict[str, Any] = {
            "metadata_": {await title_key(target_type, subtype): " ".join(text.split())},
            "status": "draft",
        }
        if subtype:
            kwargs[f"{target_type}_type"] = subtype
        cfg = (
            await session.execute(select(AdminConfig).where(AdminConfig.key == "default"))
        ).scalar_one_or_none()
        schema = (cfg.idno_schemas or {}).get(target_type) if cfg else None
        if schema:
            kwargs["idno"] = await consume_next_idno(session, target_type, schema)
        rec = model(**kwargs)
        session.add(rec)
        await session.flush()
        await log_change(
            session,
            record_type=target_type,
            record_id=rec.id,
            user_id=user_id,
            action="create",
            changed_fields={"source": "import-relation"},
        )
        report.created_records.append((target_type, rec))
        return rec

    for name, fd in relation_fields.items():
        settings = fd.settings or {}
        target_type = settings["target_type"]
        subtype = settings.get("target_subtype") or None
        fixed_type = settings.get("fixed_relation_type")
        opts = options.get(name, {})
        lookup = "label" if opts.get("lookup") == "label" else "idno"
        create = opts.get("on_missing") == "create"
        label = _field_label(fd)

        wanted = {
            item.strip()
            for record in records
            for item in _as_items(record.get(name))
            if isinstance(item, str) and item.strip()
        }
        if not wanted:
            continue
        if not fixed_type:
            for index, record in enumerate(records):
                if any(isinstance(i, str) and i.strip() for i in _as_items(record.get(name))):
                    report.error(
                        index,
                        f"Feld '{label}': kein fester Relationstyp konfiguriert, "
                        "Import aus Text nicht möglich.",
                    )
                    record.pop(name, None)
            continue
        wanted_keys = wanted if lookup == "idno" else {normalize_term_key(v) for v in wanted}
        await load_index(name, target_type, subtype, lookup, wanted_keys)
        cache = index_cache[name]

        for index, record in enumerate(records):
            value = record.get(name)
            if value is None or isinstance(value, dict):
                continue
            entries: list[Any] = []
            for item in _as_items(value):
                if isinstance(item, dict):
                    entries.append(item)
                    continue
                if not isinstance(item, str) or not item.strip():
                    continue
                text = item.strip()
                key = text if lookup == "idno" else normalize_term_key(text)
                matches = cache.get(key, [])
                if len(matches) > 1:
                    report.error(index, f"Feld '{label}': '{text}' ist mehrdeutig.")
                    continue
                if matches:
                    rec = matches[0]
                elif create:
                    rec = await create_target(target_type, subtype, text)
                    cache[key] = [rec]
                else:
                    report.error(
                        index, f"Feld '{label}': '{text}' nicht gefunden ({target_type})."
                    )
                    continue
                title = _extract_title(rec.metadata_ or {}) or rec.idno or text
                entries.append({"id": str(rec.id), "label": title, "relation_type": fixed_type})
            if not entries:
                record.pop(name, None)
            elif fd.is_repeatable:
                record[name] = entries
            elif len(entries) > 1:
                report.error(index, f"Feld '{label}': nur ein Wert erlaubt.")
                record[name] = entries[0]
            else:
                record[name] = entries[0]
    return report
