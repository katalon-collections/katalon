# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import csv
import io
import json
import logging
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
    StorageLocation,
    User,
)
from katalon.core.visibility import apply_public_visibility
from katalon.integrations.metadata_format import CompiledMappingSet, ExportRecordContext
from katalon.services.metadata_format_service import get_format
from katalon.services.metadata_mapping_service import extract_values, get_mapping_index
from katalon.services.public_metadata_service import (
    filter_public_metadata,
    load_hidden_relation_targets,
    load_public_fields,
)

logger = logging.getLogger(__name__)

RECORD_MODELS: dict[str, tuple[type[Any], str]] = {
    "object": (Object, "object_type"),
    "entity": (Entity, "entity_type"),
    "place": (Place, "place_type"),
    "occurrence": (Occurrence, "occurrence_type"),
    "procedure": (Procedure, "procedure_type"),
    "collection": (Collection, "collection_type"),
    "storage_location": (StorageLocation, "storage_location_type"),
}


# Never shown outside the authenticated API, whatever their status (internal logistics/processes).
_NEVER_PUBLIC_TYPES = frozenset({"procedure", "storage_location"})


async def _load_records(
    db: AsyncSession, record_type: str, subtype: str | None, visibility_user: User | None
) -> tuple[list[Any], list[FieldDefinition]]:
    """Load records and columns for export, restricted to what `visibility_user` may read.

    Mirrors the list-endpoint convention (`apply_public_visibility`): a user
    without record-read permission on `record_type` (including no user at
    all) only sees public/published, non-deleted rows — never draft/internal
    records, their IDs, or their field values (#389). For such a caller the
    columns are the public top-level fields only; values come from
    `_export_metadata` (public projection).
    """
    if visibility_user is None and record_type in _NEVER_PUBLIC_TYPES:
        return [], []
    model, subtype_col = RECORD_MODELS[record_type]
    query = apply_public_visibility(select(model), model, visibility_user)
    if subtype:
        query = query.where(getattr(model, subtype_col) == subtype)
    result = await db.execute(query.order_by(getattr(model, "created_at")))
    records = list(result.scalars().all())

    if visibility_user is None:
        fields = [f for f in await _public_export_fields(db, record_type) if f.parent_id is None]
        return records, fields

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


async def _public_export_fields(db: AsyncSession, record_type: str) -> list[FieldDefinition]:
    # `file` values (attachment ids, filenames) never leave through exports.
    return [f for f in await load_public_fields(db, record_type) if f.field_type != "file"]


async def _export_metadata(
    db: AsyncSession,
    record_type: str,
    records: list[Any],
    visibility_user: User | None,
) -> list[dict[str, Any]]:
    """Metadata per record as the caller may see it: raw with read permission, else projected.

    Never mutates `record.metadata_` (ORM objects would flush the projection back).
    """
    if visibility_user is not None:
        return [record.metadata_ or {} for record in records]
    if not records:
        return []
    _, subtype_col = RECORD_MODELS[record_type]
    fields = await _public_export_fields(db, record_type)
    hidden = await load_hidden_relation_targets(db, [r.metadata_ for r in records], fields)
    return [
        filter_public_metadata(r.metadata_, fields, getattr(r, subtype_col), hidden)
        for r in records
    ]


def _record_to_row(
    record: Any, metadata: dict[str, Any], subtype_col: str, fields: list[FieldDefinition]
) -> dict[str, Any]:
    src = {"idno": record.idno, "metadata": metadata}
    row: dict[str, Any] = {
        "id": str(record.id),
        "idno": record.idno or "",
        "subtype": getattr(record, subtype_col) or "",
        "status": getattr(record, "status", None),
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }
    for field in fields:
        row[field.name] = "; ".join(extract_values(src, field.name))
    return row


async def stream_csv(
    db: AsyncSession, record_type: str, subtype: str | None, visibility_user: User | None
) -> AsyncIterator[str]:
    records, fields = await _load_records(db, record_type, subtype, visibility_user)
    metadatas = await _export_metadata(db, record_type, records, visibility_user)
    _, subtype_col = RECORD_MODELS[record_type]
    columns = [
        "id",
        "idno",
        "subtype",
        "status",
        "created_at",
        "updated_at",
        *(f.name for f in fields),
    ]

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns)
    writer.writeheader()
    yield buf.getvalue()

    for record, metadata in zip(records, metadatas, strict=True):
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=columns)
        writer.writerow(_record_to_row(record, metadata, subtype_col, fields))
        yield buf.getvalue()


async def stream_json(
    db: AsyncSession, record_type: str, subtype: str | None, visibility_user: User | None
) -> AsyncIterator[str]:
    records, _fields = await _load_records(db, record_type, subtype, visibility_user)
    metadatas = await _export_metadata(db, record_type, records, visibility_user)
    _, subtype_col = RECORD_MODELS[record_type]

    yield "["
    for i, (record, metadata) in enumerate(zip(records, metadatas, strict=True)):
        if i:
            yield ","
        row: dict[str, Any] = {
            "id": str(record.id),
            "idno": record.idno,
            "subtype": getattr(record, subtype_col),
            "status": getattr(record, "status", None),
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
            "metadata": metadata,
        }
        yield json.dumps(row, default=str)
    yield "]"


async def stream_xml(
    db: AsyncSession, record_type: str, format_key: str, visibility_user: User | None
) -> AsyncIterator[str]:
    from katalon.integrations.elasticsearch import iter_hits_by_type
    from katalon.services.export_context_service import refresh_index_contexts

    metadata_format = await get_format(format_key)
    if metadata_format is None:
        raise ValueError(f"Unbekanntes Export-Format '{format_key}'.")

    mapping_index = await get_mapping_index(db, format_key)
    record_mappings = mapping_index.get(record_type)
    if record_mappings is None:
        record_mappings = CompiledMappingSet(format_key=format_key, record_type=record_type)
    header, footer = metadata_format.render_batch_envelope()
    yield header
    skipped: list[str] = []
    async for hit in iter_hits_by_type(record_type, public_only=visibility_user is None):
        await refresh_index_contexts(db, [hit])
        ctx = ExportRecordContext.from_hit(hit)
        missing = metadata_format.required_field_errors(ctx, record_mappings)
        if missing:
            record_ref = ctx.record.idno or str(ctx.record.id)
            logger.warning(
                "Export %s: Datensatz %s übersprungen (Pflichtfelder fehlen): %s",
                format_key, record_ref, "; ".join(missing),
            )
            skipped.append(record_ref)
            continue
        el = metadata_format.render_batch_item(ctx, record_mappings)
        yield ET.tostring(el, encoding="unicode") + "\n"
    if skipped:
        comment = f"{len(skipped)} Datensatz/Datensätze übersprungen (Pflichtfelder fehlen): {', '.join(skipped)}"
        yield f"<!-- {comment.replace('--', '—')} -->\n"
    yield footer
