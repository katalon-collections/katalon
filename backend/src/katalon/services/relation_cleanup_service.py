# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def _without_deleted_reference(value: Any, deleted_id: uuid.UUID) -> tuple[Any, bool]:
    if isinstance(value, list):
        filtered = [
            entry
            for entry in value
            if not (isinstance(entry, dict) and str(entry.get("id")) == str(deleted_id))
        ]
        return filtered, len(filtered) != len(value)
    if isinstance(value, dict) and str(value.get("id")) == str(deleted_id):
        return None, True
    return value, False


async def cleanup_relation_refs(
    session: AsyncSession,
    deleted_type: str,
    deleted_id: uuid.UUID,
    *,
    cutoff: datetime | None = None,
) -> int:
    """Remove references to a hard-deleted record from configured relation fields."""
    from katalon.core.models import (
        Collection,
        Entity,
        FieldDefinition,
        Object,
        Occurrence,
        Place,
        Procedure,
        StorageLocation,
    )
    from katalon.services.audit_service import diff_fields, log_change
    from katalon.services.search_service import index_record

    fields = (
        (
            await session.execute(
                select(FieldDefinition).where(
                    FieldDefinition.field_type.in_(("relation", "group")),
                    FieldDefinition.is_deleted.is_(False),
                )
            )
        )
        .scalars()
        .all()
    )
    groups = {
        field.id: field
        for field in fields
        if field.field_type == "group" and field.parent_id is None
    }
    direct_fields: dict[str, list[str]] = {}
    group_fields: dict[str, list[tuple[str, str]]] = {}
    for field in fields:
        if (
            field.field_type != "relation"
            or (field.settings or {}).get("target_type") != deleted_type
        ):
            continue
        if field.parent_id is None:
            direct_fields.setdefault(field.target_type, []).append(field.name)
            continue
        parent = groups.get(field.parent_id)
        if parent is not None and parent.target_type == field.target_type:
            group_fields.setdefault(field.target_type, []).append((parent.name, field.name))

    model_map: dict[str, Any] = {
        "object": Object,
        "entity": Entity,
        "place": Place,
        "occurrence": Occurrence,
        "procedure": Procedure,
        "collection": Collection,
        "storage_location": StorageLocation,
    }
    cleaned = 0
    for source_type, model in model_map.items():
        source_direct = direct_fields.get(source_type, [])
        source_groups = group_fields.get(source_type, [])
        if not source_direct and not source_groups:
            continue
        records = (await session.execute(select(model))).scalars().all()
        for record in records:
            if source_type == deleted_type and record.id == deleted_id:
                continue
            if (
                cutoff is not None
                and getattr(record, "deleted_at", None) is not None
                and record.deleted_at < cutoff
            ):
                continue
            old_metadata = record.metadata_ or {}
            metadata = deepcopy(old_metadata)
            modified = False
            for field_name in source_direct:
                value, changed = _without_deleted_reference(metadata.get(field_name), deleted_id)
                if changed:
                    metadata[field_name] = value
                    modified = True
            for group_name, field_name in source_groups:
                instances = metadata.get(group_name)
                if not isinstance(instances, list):
                    continue
                for instance in instances:
                    if not isinstance(instance, dict):
                        continue
                    value, changed = _without_deleted_reference(
                        instance.get(field_name), deleted_id
                    )
                    if changed:
                        instance[field_name] = value
                        modified = True
            if not modified:
                continue
            record.metadata_ = metadata
            await log_change(
                session,
                record_type=source_type,
                record_id=record.id,
                user_id=None,
                action="relation_cleanup",
                changed_fields=diff_fields({"metadata": old_metadata}, {"metadata": metadata}),
            )
            await index_record(source_type, record, session)
            cleaned += 1
    return cleaned
