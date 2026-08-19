from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import FieldDefinition, MetadataMapping

OAI_DC_FORMAT = "oai_dc"
OAI_DC_TARGETS = {
    "dc:title",
    "dc:creator",
    "dc:subject",
    "dc:description",
    "dc:publisher",
    "dc:contributor",
    "dc:date",
    "dc:type",
    "dc:format",
    "dc:identifier",
    "dc:source",
    "dc:language",
    "dc:relation",
    "dc:coverage",
    "dc:rights",
}

MappingIndex = dict[str, dict[str, list[str]]]


def validate_mapping_target(format_key: str, target_path: str) -> None:
    if format_key == OAI_DC_FORMAT and target_path not in OAI_DC_TARGETS:
        allowed = ", ".join(sorted(OAI_DC_TARGETS))
        raise ValueError(f"Ungültiges OAI-DC-Ziel '{target_path}'. Erlaubt: {allowed}")


async def get_mappings(
    db: AsyncSession,
    *,
    format_key: str | None = None,
    field_definition_id: uuid.UUID | None = None,
) -> list[MetadataMapping]:
    q = select(MetadataMapping)
    if format_key:
        q = q.where(MetadataMapping.format_key == format_key)
    if field_definition_id:
        q = q.where(MetadataMapping.field_definition_id == field_definition_id)
    result = await db.execute(q.order_by(MetadataMapping.format_key, MetadataMapping.sort_order))
    return list(result.scalars().all())


async def get_mapping_index(db: AsyncSession, format_key: str) -> MappingIndex:
    result = await db.execute(
        select(MetadataMapping, FieldDefinition)
        .join(FieldDefinition, MetadataMapping.field_definition_id == FieldDefinition.id)
        .where(
            MetadataMapping.format_key == format_key,
            MetadataMapping.is_enabled.is_(True),
            FieldDefinition.is_deleted.is_(False),
        )
        .order_by(
            FieldDefinition.target_type,
            MetadataMapping.sort_order,
            FieldDefinition.sort_order,
        )
    )
    index: MappingIndex = defaultdict(lambda: defaultdict(list[Any]))
    for mapping, field in result.all():
        index[field.target_type][field.name].append(mapping.target_path)
    return {record_type: dict(fields) for record_type, fields in index.items()}


def extract_values(src: dict[str, Any], field_name: str) -> list[str]:
    md = src.get("metadata", {}) or {}
    raw = md.get(field_name)
    if raw is None and field_name in {"idno", "title", "created_at", "updated_at"}:
        raw = src.get(field_name)
    values = _flatten_value(raw)
    return [v for v in values if v]


def _flatten_value(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_flatten_value(item))
        return out
    if isinstance(value, dict):
        for key in ("value", "label", "term", "name", "title", "idno"):
            if key not in value:
                continue
            nested = value[key]
            if isinstance(nested, dict):
                text = nested.get("de") or nested.get("en") or next(
                    (str(v) for v in nested.values() if v),
                    "",
                )
                return [text] if text else []
            return _flatten_value(nested)
        return []
    return [str(value)]
