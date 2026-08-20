"""Server-side projection for metadata exposed without authentication."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import FieldDefinition


async def load_public_fields(db: AsyncSession, target_type: str) -> list[FieldDefinition]:
    """Load active fields whose values may leave the authenticated API."""
    result = await db.execute(
        select(FieldDefinition).where(
            FieldDefinition.target_type == target_type,
            FieldDefinition.is_deleted.is_(False),
            FieldDefinition.is_public.is_(True),
        )
    )
    return list(result.scalars().all())


def filter_public_metadata(
    metadata: dict[str, Any] | None,
    fields: Iterable[FieldDefinition],
    target_subtype: str | None = None,
) -> dict[str, Any]:
    """Return only configured public fields, including public children of groups."""
    source = metadata or {}
    applicable = [
        field for field in fields
        if field.target_subtype is None or field.target_subtype == target_subtype
    ]
    top_level = [field for field in applicable if field.parent_id is None]
    children_by_parent: dict[object, set[str]] = {}
    for field in applicable:
        if field.parent_id is not None:
            children_by_parent.setdefault(field.parent_id, set()).add(field.name)

    projected: dict[str, Any] = {}
    for field in top_level:
        value = source.get(field.name)
        if value is None:
            continue
        if field.field_type != "group":
            projected[field.name] = value
            continue
        child_names = children_by_parent.get(field.id, set())
        if not child_names or not isinstance(value, list):
            continue
        entries = [
            {name: item[name] for name in child_names if name in item}
            for item in value
            if isinstance(item, dict)
        ]
        entries = [entry for entry in entries if entry]
        if entries:
            projected[field.name] = entries
    return projected


async def project_public_record(
    db: AsyncSession,
    record: BaseModel,
    target_type: str,
    target_subtype: str | None = None,
) -> BaseModel:
    """Return a response-model copy with internal metadata removed."""
    fields = await load_public_fields(db, target_type)
    metadata = filter_public_metadata(
        getattr(record, "metadata_", None), fields, target_subtype
    )
    return record.model_copy(update={"metadata_": metadata})
