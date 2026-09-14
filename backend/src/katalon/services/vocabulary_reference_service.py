# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import uuid
from collections.abc import Iterator
from copy import deepcopy
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import FieldDefinition, VocabularyTerm
from katalon.services.relation_service import _RECORD_MODELS


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
        from katalon.workers.index_tasks import bulk_reindex_type_task

        for record_type in changed_types:
            after_commit(db, bulk_reindex_type_task, record_type)
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
        from katalon.workers.index_tasks import bulk_reindex_type_task

        for record_type in changed_types:
            after_commit(db, bulk_reindex_type_task, record_type)

    return removed
