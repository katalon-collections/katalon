# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import csv
import io
import json
import xml.etree.ElementTree as ET
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import (
    Collection,
    Entity,
    FieldDefinition,
    Object,
    Occurrence,
    Place,
    Procedure,
)
from katalon.services.metadata_format_service import get_format
from katalon.services.metadata_mapping_service import extract_values, get_mapping_index

RECORD_MODELS: dict[str, tuple[type[Any], str]] = {
    "object": (Object, "object_type"),
    "entity": (Entity, "entity_type"),
    "place": (Place, "place_type"),
    "occurrence": (Occurrence, "occurrence_type"),
    "procedure": (Procedure, "procedure_type"),
    "collection": (Collection, "collection_type"),
}


async def _load_records(
    db: AsyncSession, record_type: str, subtype: str | None
) -> tuple[list[Any], list[FieldDefinition]]:
    model, subtype_col = RECORD_MODELS[record_type]
    query = select(model).where(getattr(model, "deleted_at").is_(None))
    if subtype:
        query = query.where(getattr(model, subtype_col) == subtype)
    result = await db.execute(query.order_by(getattr(model, "created_at")))
    records = list(result.scalars().all())

    fields_result = await db.execute(
        select(FieldDefinition)
        .where(
            FieldDefinition.target_type == record_type,
            FieldDefinition.is_deleted.is_(False),
            FieldDefinition.parent_id.is_(None),
        )
        .order_by(FieldDefinition.sort_order)
    )
    fields = list(fields_result.scalars().all())
    return records, fields


def _record_to_row(record: Any, subtype_col: str, fields: list[FieldDefinition]) -> dict[str, Any]:
    src = {"idno": record.idno, "metadata": record.metadata_}
    row: dict[str, Any] = {
        "id": str(record.id),
        "idno": record.idno or "",
        "subtype": getattr(record, subtype_col) or "",
        "status": record.status,
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }
    for field in fields:
        row[field.name] = "; ".join(extract_values(src, field.name))
    return row


async def stream_csv(db: AsyncSession, record_type: str, subtype: str | None) -> AsyncIterator[str]:
    records, fields = await _load_records(db, record_type, subtype)
    _, subtype_col = RECORD_MODELS[record_type]
    columns = ["id", "idno", "subtype", "status", "created_at", "updated_at", *(f.name for f in fields)]

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns)
    writer.writeheader()
    yield buf.getvalue()

    for record in records:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=columns)
        writer.writerow(_record_to_row(record, subtype_col, fields))
        yield buf.getvalue()


async def stream_json(db: AsyncSession, record_type: str, subtype: str | None) -> AsyncIterator[str]:
    records, fields = await _load_records(db, record_type, subtype)
    _, subtype_col = RECORD_MODELS[record_type]

    yield "["
    for i, record in enumerate(records):
        if i:
            yield ","
        row: dict[str, Any] = {
            "id": str(record.id),
            "idno": record.idno,
            "subtype": getattr(record, subtype_col),
            "status": record.status,
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
            "metadata": record.metadata_,
        }
        yield json.dumps(row, default=str)
    yield "]"


async def stream_xml(db: AsyncSession, record_type: str, format_key: str) -> AsyncIterator[str]:
    from katalon.integrations.elasticsearch import iter_hits_by_type

    metadata_format = await get_format(format_key)
    if metadata_format is None:
        raise ValueError(f"Unbekanntes Export-Format '{format_key}'.")

    mapping_index = await get_mapping_index(db, format_key)
    record_mappings = mapping_index.get(record_type, {})

    yield '<?xml version="1.0" encoding="UTF-8"?>\n<collection>\n'
    async for hit in iter_hits_by_type(record_type):
        el = metadata_format.render(hit, record_mappings)
        yield ET.tostring(el, encoding="unicode") + "\n"
    yield "</collection>\n"
