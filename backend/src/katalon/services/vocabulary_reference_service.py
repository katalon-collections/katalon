# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import uuid
from collections.abc import Iterator
from copy import deepcopy
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import FieldDefinition, Vocabulary, VocabularyTerm
from katalon.services.relation_service import _RECORD_MODELS

SYSTEM_VOCABULARY_NAMES: frozenset[str] = frozenset({"media_types", "relation_types"})


async def referencing_schema_fields(
    db: AsyncSession, vocabulary_id: uuid.UUID
) -> list[FieldDefinition]:
    """Return active record schema fields referencing ``vocabulary_id``."""
    vocab_id_str = str(vocabulary_id)
    fields = list(
        (
            await db.execute(
                select(FieldDefinition).where(
                    FieldDefinition.is_deleted.is_(False),
                    FieldDefinition.field_type.in_(("vocab", "vocab_free", "relation")),
                )
            )
        ).scalars()
    )
    return [
        f
        for f in fields
        if (
            f.field_type in ("vocab", "vocab_free")
            and str((f.settings or {}).get("vocabulary_id")) == vocab_id_str
        )
        or (
            f.field_type == "relation"
            and str((f.settings or {}).get("relation_type_vocab")) == vocab_id_str
        )
    ]


async def ensure_field_vocabulary(db: AsyncSession, field: FieldDefinition, vocab_name: str) -> None:
    """Bind a vocab field without vocabulary to the vocabulary ``vocab_name`` (created if
    missing). Without a binding the field rejects every imported value."""
    if field.field_type != "vocab" or (field.settings or {}).get("vocabulary_id"):
        return
    vocab = (await db.execute(select(Vocabulary).where(Vocabulary.name == vocab_name))).scalar_one_or_none()
    if vocab is None:
        vocab = Vocabulary(name=vocab_name)
        db.add(vocab)
        await db.flush()
    field.settings = {**(field.settings or {}), "vocabulary_id": str(vocab.id)}


async def count_vocabulary_terms(db: AsyncSession, vocabulary_id: uuid.UUID) -> int:
    """Count all terms belonging to ``vocabulary_id``."""
    result = await db.execute(
        select(func.count()).where(VocabularyTerm.vocabulary_id == vocabulary_id)
    )
    return result.scalar_one()


async def clear_vocabulary_terms(db: AsyncSession, vocabulary_id: uuid.UUID) -> int:
    """Delete all terms of ``vocabulary_id`` while keeping the vocabulary row itself."""
    term_count = await count_vocabulary_terms(db, vocabulary_id)
    if term_count > 0:
        await request_reindex_for_vocabulary(db, vocabulary_id)
        await db.execute(
            delete(VocabularyTerm).where(VocabularyTerm.vocabulary_id == vocabulary_id)
        )
    return term_count


async def delete_vocabulary_and_terms(
    db: AsyncSession, vocab: Vocabulary, *, force: bool = False
) -> tuple[int, int]:
    """Delete ``vocab`` and all its terms, optionally soft-deleting referencing schema fields.

    Returns ``(deleted_terms, deactivated_fields)``.
    """
    from katalon.workers.enqueue import after_commit
    from katalon.workers.reindex_state import request_bulk_reindex

    ref_fields = await referencing_schema_fields(db, vocab.id)
    deactivated_fields = 0
    affected_types: set[str] = set()
    if ref_fields and force:
        for field in ref_fields:
            field.is_deleted = True
            deactivated_fields += 1
            if field.target_type in _RECORD_MODELS:
                affected_types.add(field.target_type)

    # Also soft-delete any custom vocabulary_term fields scoped to this vocabulary
    await db.execute(
        update(FieldDefinition)
        .where(
            FieldDefinition.target_type == "vocabulary_term",
            FieldDefinition.target_subtype == str(vocab.id),
            FieldDefinition.is_deleted.is_(False),
        )
        .values(is_deleted=True)
    )

    term_count = await count_vocabulary_terms(db, vocab.id)
    for record_type, fields in (await _vocab_fields(db, vocab.id)).items():
        if fields:
            affected_types.add(record_type)

    await db.execute(
        delete(VocabularyTerm).where(VocabularyTerm.vocabulary_id == vocab.id)
    )
    await db.delete(vocab)

    for record_type in affected_types:
        after_commit(db, request_bulk_reindex, record_type)

    return term_count, deactivated_fields


async def count_direct_children(db: AsyncSession, parent_id: uuid.UUID) -> int:
    """Count vocabulary terms directly nested under ``parent_id``."""
    result = await db.execute(
        select(func.count()).where(VocabularyTerm.parent_id == parent_id)
    )
    return result.scalar_one()


async def reparent_children(
    db: AsyncSession, parent_id: uuid.UUID, new_parent_id: uuid.UUID | None
) -> None:
    """Move direct children of ``parent_id`` to ``new_parent_id``."""
    await db.execute(
        update(VocabularyTerm)
        .where(VocabularyTerm.parent_id == parent_id)
        .values(parent_id=new_parent_id)
    )


async def get_term_subtree_ids(db: AsyncSession, root_id: uuid.UUID) -> list[uuid.UUID]:
    """Return root_id and all its recursive descendant vocabulary term IDs."""
    base_query = select(VocabularyTerm.id).where(VocabularyTerm.id == root_id)
    cte = base_query.cte(name="vocabulary_term_subtree", recursive=True)
    child_query = select(VocabularyTerm.id).join(cte, VocabularyTerm.parent_id == cte.c.id)
    cte = cte.union_all(child_query)
    result = await db.execute(select(cte.c.id))
    return list(result.scalars().all())


def _references(value: object, term_id: uuid.UUID) -> Iterator[dict[str, Any]]:
    values = value if isinstance(value, list) else [value]
    for entry in values:
        if isinstance(entry, dict) and entry.get("id") == str(term_id):
            yield entry


async def _vocab_fields(
    db: AsyncSession, vocabulary_id: uuid.UUID
) -> dict[str, list[tuple[str | None, FieldDefinition]]]:
    fields = list(
        (
            await db.execute(
                select(FieldDefinition).where(
                    FieldDefinition.is_deleted.is_(False),
                    FieldDefinition.field_type == "vocab",
                )
            )
        ).scalars()
    )
    selected = [
        field
        for field in fields
        if str((field.settings or {}).get("vocabulary_id")) == str(vocabulary_id)
    ]
    parent_ids = {field.parent_id for field in selected if field.parent_id is not None}
    parents = (
        {
            field.id: field
            for field in (
                await db.execute(select(FieldDefinition).where(FieldDefinition.id.in_(parent_ids)))
            ).scalars()
        }
        if parent_ids
        else {}
    )
    result: dict[str, list[tuple[str | None, FieldDefinition]]] = {
        record_type: [] for record_type in _RECORD_MODELS
    }
    for field in selected:
        parent = parents.get(field.parent_id)
        result[field.target_type].append((parent.name if parent else None, field))
    return result


async def request_reindex_for_vocabulary(db: AsyncSession, vocabulary_id: uuid.UUID) -> None:
    """Rebuild every record type with a field on this vocabulary (after commit).

    Hierarchical vocabulary facets index each value's ancestor path, so moving
    a term (new parent) changes documents without touching record metadata.
    """
    from katalon.workers.enqueue import after_commit
    from katalon.workers.reindex_state import request_bulk_reindex

    for record_type, fields in (await _vocab_fields(db, vocabulary_id)).items():
        if fields:
            after_commit(db, request_bulk_reindex, record_type)


def _record_references(
    metadata: dict[str, Any], fields: list[tuple[str | None, FieldDefinition]], term_id: uuid.UUID
) -> Iterator[dict[str, Any]]:
    for parent_name, field in fields:
        if parent_name is None:
            yield from _references(metadata.get(field.name), term_id)
            continue
        for instance in metadata.get(parent_name, []):
            if isinstance(instance, dict):
                yield from _references(instance.get(field.name), term_id)


async def count_references(db: AsyncSession, vocabulary_id: uuid.UUID, term_id: uuid.UUID) -> int:
    fields_by_type = await _vocab_fields(db, vocabulary_id)
    count = 0
    for record_type, model in _RECORD_MODELS.items():
        fields = fields_by_type[record_type]
        if not fields:
            continue
        records = (await db.execute(select(model.metadata_))).scalars()
        for metadata in records:
            count += sum(1 for _ in _record_references(metadata or {}, fields, term_id))
    return count


async def remap_references(
    db: AsyncSession,
    vocabulary_id: uuid.UUID,
    source_id: uuid.UUID,
    replacement: VocabularyTerm,
) -> int:
    fields_by_type = await _vocab_fields(db, vocabulary_id)
    updated = 0
    changed_types: set[str] = set()
    replacement_label = (
        replacement.label.get("de") or replacement.label.get("en") or replacement.term
    )
    for record_type, model in _RECORD_MODELS.items():
        fields = fields_by_type[record_type]
        if not fields:
            continue
        records = (await db.execute(select(model))).scalars()
        for record in records:
            metadata = deepcopy(record.metadata_ or {})
            changed = False
            for entry in _record_references(metadata, fields, source_id):
                entry["id"] = str(replacement.id)
                entry["label"] = replacement_label
                changed = True
                updated += 1
            if changed:
                record.metadata_ = metadata
                changed_types.add(record_type)
    if changed_types:
        from katalon.workers.enqueue import after_commit
        from katalon.workers.reindex_state import request_bulk_reindex

        for record_type in changed_types:
            after_commit(db, request_bulk_reindex, record_type)
    return updated


def _remove_term_from_value(value: Any, term_id_str: str) -> tuple[Any, int]:
    if isinstance(value, list):
        filtered = [
            item
            for item in value
            if not (
                (isinstance(item, dict) and str(item.get("id")) == term_id_str)
                or (isinstance(item, str) and item == term_id_str)
            )
        ]
        return filtered, len(value) - len(filtered)
    if isinstance(value, dict) and str(value.get("id")) == term_id_str:
        return None, 1
    if isinstance(value, str) and value == term_id_str:
        return None, 1
    return value, 0


async def remove_references(
    db: AsyncSession,
    vocabulary_id: uuid.UUID,
    term_id: uuid.UUID,
) -> int:
    fields_by_type = await _vocab_fields(db, vocabulary_id)
    removed = 0
    changed_types: set[str] = set()
    term_id_str = str(term_id)

    for record_type, model in _RECORD_MODELS.items():
        fields = fields_by_type[record_type]
        if not fields:
            continue
        records = (await db.execute(select(model))).scalars()
        for record in records:
            metadata = deepcopy(record.metadata_ or {})
            changed = False

            for parent_name, field in fields:
                if parent_name is None:
                    if field.name in metadata:
                        val = metadata.get(field.name)
                        new_val, removed_cnt = _remove_term_from_value(val, term_id_str)
                        if removed_cnt > 0:
                            if new_val is None:
                                metadata.pop(field.name, None)
                            else:
                                metadata[field.name] = new_val
                            removed += removed_cnt
                            changed = True
                else:
                    instances = metadata.get(parent_name)
                    if isinstance(instances, list):
                        for instance in instances:
                            if isinstance(instance, dict) and field.name in instance:
                                sub_val = instance.get(field.name)
                                new_sub_val, removed_cnt = _remove_term_from_value(
                                    sub_val, term_id_str
                                )
                                if removed_cnt > 0:
                                    if new_sub_val is None:
                                        instance.pop(field.name, None)
                                    else:
                                        instance[field.name] = new_sub_val
                                    removed += removed_cnt
                                    changed = True

            if changed:
                record.metadata_ = metadata
                changed_types.add(record_type)

    if changed_types:
        from katalon.workers.enqueue import after_commit
        from katalon.workers.reindex_state import request_bulk_reindex

        for record_type in changed_types:
            after_commit(db, request_bulk_reindex, record_type)

    return removed
