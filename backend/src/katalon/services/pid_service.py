from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.config import settings
from katalon.core.models import Entity, FieldDefinition, Object, Occurrence, Place
from katalon.integrations.dnb_urn_adapter import DnbUrnAdapter

RecordModel = Object | Entity | Place | Occurrence

_MODEL_BY_TYPE: dict[str, type[Object] | type[Entity] | type[Place] | type[Occurrence]] = {
    "object": Object,
    "entity": Entity,
    "place": Place,
    "occurrence": Occurrence,
}


def _resolver_link(urn: str) -> str:
    return f"{settings.dnb_urn_resolver_url.rstrip('/')}/{urn}"


async def register_dnb_urn_for_record(
    db: AsyncSession,
    record_type: str,
    record_id: uuid.UUID,
    field_name: str,
    target_url: str,
    label: str = "URN",
) -> dict[str, Any]:
    if record_type != "object":
        raise ValueError("URN-Registrierung ist nur für Objekte erlaubt.")

    model = _MODEL_BY_TYPE.get(record_type)
    if model is None:
        raise ValueError("Ungültiger record_type.")

    record_result = await db.execute(select(model).where(model.id == record_id))
    record: RecordModel | None = record_result.scalar_one_or_none()
    if record is None:
        raise LookupError("Datensatz nicht gefunden.")

    field_result = await db.execute(
        select(FieldDefinition).where(
            FieldDefinition.target_type == record_type,
            FieldDefinition.name == field_name,
            FieldDefinition.field_type == "pid",
            FieldDefinition.is_deleted.is_(False),
        )
    )
    field = field_result.scalar_one_or_none()
    if field is None:
        raise LookupError("PID-Feld nicht gefunden.")

    adapter = DnbUrnAdapter()
    urn = await adapter.mint_and_register(target_url=target_url)
    value = {"value": urn, "label": label}

    metadata = dict(record.metadata_ or {})
    if field.is_repeatable:
        existing = metadata.get(field_name)
        entries = list(existing) if isinstance(existing, list) else []
        if not any(isinstance(item, dict) and item.get("value") == urn for item in entries):
            entries.append(value)
        metadata[field_name] = entries
    else:
        metadata[field_name] = value
    record.metadata_ = metadata
    await db.flush()

    return {
        "urn": urn,
        "resolver_url": _resolver_link(urn),
        "value": value,
        "metadata": metadata,
    }
