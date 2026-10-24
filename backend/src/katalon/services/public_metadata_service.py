# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Server-side projection for metadata exposed without authentication."""

from __future__ import annotations

import uuid
from collections.abc import Collection as AbstractCollection
from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import Collection, Entity, FieldDefinition, Object, Occurrence, Place
from katalon.core.visibility import PUBLIC_STATUSES

_RELATION_TARGET_MODELS: dict[str, Any] = {
    "object": Object,
    "entity": Entity,
    "place": Place,
    "occurrence": Occurrence,
    "collection": Collection,
}


async def load_public_fields(db: AsyncSession, target_type: str) -> list[FieldDefinition]:
    """Load active fields whose values may leave the authenticated API."""
    result = await db.execute(
        select(FieldDefinition).where(
            FieldDefinition.target_type == target_type,
            FieldDefinition.is_deleted.is_(False),
            FieldDefinition.is_public.is_(True),
        ).order_by(FieldDefinition.sort_order, FieldDefinition.name)
    )
    return list(result.scalars().all())


def _relation_entries(value: Any) -> list[dict[str, Any]]:
    """Entries of a relation field value ({id, label, relation_type} or a list of them)."""
    items = value if isinstance(value, list) else [value]
    return [item for item in items if isinstance(item, dict)]


def _public_relation_value(value: Any, hidden_targets: AbstractCollection[str] | None) -> Any:
    """Drop entries whose target is not public; None when nothing is left.

    Without `hidden_targets` the caller did not check target visibility, so no entry
    may leave: the stored label would expose drafts and internal records.
    """
    if hidden_targets is None:
        return None
    kept = [e for e in _relation_entries(value) if str(e.get("id", "")) not in hidden_targets]
    if not kept:
        return None
    return kept if isinstance(value, list) else kept[0]


def relation_target_ids(
    metadata: dict[str, Any] | None, fields: Iterable[FieldDefinition]
) -> dict[str, set[str]]:
    """Target ids per record type referenced by the relation fields (and group children) in `metadata`."""
    source = metadata or {}
    fields = list(fields)
    by_id = {getattr(field, "id", None): field for field in fields}
    wanted: dict[str, set[str]] = {}
    for field in fields:
        if field.field_type != "relation":
            continue
        target_type = str((getattr(field, "settings", None) or {}).get("target_type") or "")
        parent_id = getattr(field, "parent_id", None)
        parent = by_id.get(parent_id) if parent_id is not None else None
        if parent is None:
            values = [source.get(field.name)]
        else:
            group_value = source.get(parent.name)
            values = [item.get(field.name) for item in group_value or [] if isinstance(item, dict)]
        for value in values:
            for entry in _relation_entries(value):
                if entry.get("id"):
                    wanted.setdefault(target_type, set()).add(str(entry["id"]))
    return wanted


async def visible_record_ids(
    db: AsyncSession, ids_by_type: dict[str, set[uuid.UUID]]
) -> set[tuple[str, uuid.UUID]]:
    """(type, id) pairs that are public, not deleted and of a portal record type."""
    visible: set[tuple[str, uuid.UUID]] = set()
    for record_type, ids in ids_by_type.items():
        model = _RELATION_TARGET_MODELS.get(record_type)
        if model is None or not ids:
            continue
        rows = await db.execute(
            select(model.id).where(
                model.id.in_(list(ids)),
                model.status.in_(PUBLIC_STATUSES),
                model.deleted_at.is_(None),
            )
        )
        visible.update((record_type, row) for row in rows.scalars().all())
    return visible


async def load_hidden_relation_targets(
    db: AsyncSession,
    metadatas: Iterable[dict[str, Any] | None],
    fields: Iterable[FieldDefinition],
) -> set[str]:
    """Ids in relation field values whose target is missing, deleted or not public."""
    fields = list(fields)
    wanted: dict[str, set[str]] = {}
    for metadata in metadatas:
        for target_type, ids in relation_target_ids(metadata, fields).items():
            wanted.setdefault(target_type, set()).update(ids)
    hidden: set[str] = set()
    valid: dict[str, set[uuid.UUID]] = {}
    for target_type, ids in wanted.items():
        for raw in ids:
            try:
                valid.setdefault(target_type, set()).add(uuid.UUID(raw))
            except ValueError:
                hidden.add(raw)
    visible = await visible_record_ids(db, valid) if valid else set()
    for target_type, uuids in valid.items():
        hidden.update(str(v) for v in uuids if (target_type, v) not in visible)
    return hidden


def filter_public_metadata(
    metadata: dict[str, Any] | None,
    fields: Iterable[FieldDefinition],
    target_subtype: str | None = None,
    hidden_targets: AbstractCollection[str] | None = None,
) -> dict[str, Any]:
    """Return only configured public fields, including public children of groups.

    Keys keep the order of ``fields`` (schema order from `load_public_fields`). The
    projection must not depend on the process: the API (preview) and the worker (index,
    OAI) build the same record, and exporters that take the first value of a group
    would otherwise differ between the two.

    Relation field entries pointing at a target in `hidden_targets` (see
    `load_hidden_relation_targets`) are dropped; callers that pass no `hidden_targets`
    get no relation field values at all.
    """
    source = metadata or {}
    applicable = [
        field for field in fields
        if field.target_subtype is None or field.target_subtype == target_subtype
    ]
    top_level = [field for field in applicable if field.parent_id is None]
    children_by_parent: dict[object, list[FieldDefinition]] = {}
    for field in applicable:
        if field.parent_id is not None:
            children = children_by_parent.setdefault(field.parent_id, [])
            if all(child.name != field.name for child in children):
                children.append(field)

    projected: dict[str, Any] = {}
    for field in top_level:
        value = source.get(field.name)
        if value is None:
            continue
        if field.field_type == "relation":
            value = _public_relation_value(value, hidden_targets)
            if value is not None:
                projected[field.name] = value
            continue
        if field.field_type != "group":
            projected[field.name] = value
            continue
        children = children_by_parent.get(field.id, [])
        if not children or not isinstance(value, list):
            continue
        entries = []
        for item in value:
            if not isinstance(item, dict):
                continue
            entry: dict[str, Any] = {}
            for child in children:
                if child.name not in item:
                    continue
                child_value = item[child.name]
                if child.field_type == "relation":
                    child_value = _public_relation_value(child_value, hidden_targets)
                    if child_value is None:
                        continue
                entry[child.name] = child_value
            if entry:
                entries.append(entry)
        if entries:
            projected[field.name] = entries
    return projected


async def filter_public_metadata_checked(
    db: AsyncSession,
    metadata: dict[str, Any] | None,
    fields: Iterable[FieldDefinition],
    target_subtype: str | None = None,
) -> dict[str, Any]:
    """`filter_public_metadata` with relation targets checked for visibility (one record)."""
    fields = list(fields)
    hidden = await load_hidden_relation_targets(db, [metadata], fields)
    return filter_public_metadata(metadata, fields, target_subtype, hidden)


async def project_public_record[T: BaseModel](
    db: AsyncSession,
    record: T,
    target_type: str,
    target_subtype: str | None = None,
    fields: list[FieldDefinition] | None = None,
    hidden_targets: AbstractCollection[str] | None = None,
) -> T:
    """Return a response-model copy with internal metadata removed.

    Batch callers pass `fields` (from `load_public_fields`) and `hidden_targets` (from
    `load_hidden_relation_targets` over all records) to load them once.
    """
    if fields is None:
        fields = await load_public_fields(db, target_type)
    if hidden_targets is None:
        hidden_targets = await load_hidden_relation_targets(
            db, [getattr(record, "metadata_", None)], fields
        )
    metadata = filter_public_metadata(
        getattr(record, "metadata_", None), fields, target_subtype, hidden_targets
    )
    updates: dict[str, Any] = {"metadata_": metadata}
    ai_provenance = getattr(record, "ai_provenance", None)
    if ai_provenance:
        updates["ai_provenance"] = filter_public_ai_provenance(ai_provenance, metadata)
    return record.model_copy(update=updates)


def filter_public_ai_provenance(
    ai_provenance: dict[str, Any], public_metadata: dict[str, Any]
) -> dict[str, Any]:
    """Keep only provenance entries whose field (or group subfield) survived
    the public metadata projection, so AI disclosure never leaks the
    existence of non-public field values."""
    filtered: dict[str, Any] = {}
    for path, info in ai_provenance.items():
        parts = path.split(".")
        top = public_metadata.get(parts[0])
        if top is None:
            continue
        if len(parts) == 1:
            filtered[path] = info
            continue
        if len(parts) == 3 and isinstance(top, list):
            try:
                index = int(parts[1])
                entry = top[index]
            except (ValueError, IndexError):
                continue
            if isinstance(entry, dict) and parts[2] in entry:
                filtered[path] = info
    return filtered
