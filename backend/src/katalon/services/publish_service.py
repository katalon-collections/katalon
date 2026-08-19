from __future__ import annotations

from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.concurrency import flush_record
from katalon.core.models import Entity, Object, Occurrence, Place
from katalon.services.audit_service import log_change
from katalon.services.schema_service import validate_metadata
from katalon.services.search_service import index_record

MODEL_MAP: dict[str, type[Object] | type[Entity] | type[Place] | type[Occurrence]] = {
    "object": Object,
    "entity": Entity,
    "place": Place,
    "occurrence": Occurrence,
}


async def can_publish(
    db: AsyncSession,
    record_type: str,
    record_id: str,
) -> tuple[bool, list[str]]:
    """Check if a record can be published. Returns (ok, errors).

    Validates:
    - idno is set
    - all required metadata fields are filled
    - metadata passes type validation
    """
    model = MODEL_MAP.get(record_type)
    if model is None:
        return False, [f"Unbekannter Typ: {record_type}"]

    result = await db.execute(select(model).where(model.id == record_id))
    rec = cast(Object | Entity | Place | Occurrence | None, result.scalar_one_or_none())
    if rec is None:
        return False, ["Datensatz nicht gefunden"]

    errors: list[str] = []

    # idno must be set
    idno = getattr(rec, "idno", None)
    if not idno or not str(idno).strip():
        errors.append("ID-Nummer ist für die Veröffentlichung erforderlich.")

    # Metadata validation
    metadata = getattr(rec, "metadata_", None) or {}
    subtype = None
    if record_type == "object":
        subtype = getattr(rec, "object_type", None)
    elif record_type == "entity":
        subtype = getattr(rec, "entity_type", None)
    elif record_type == "place":
        subtype = getattr(rec, "place_type", None)
    elif record_type == "occurrence":
        subtype = getattr(rec, "occurrence_type", None)

    val_errors = await validate_metadata(db, record_type, metadata, subtype)
    errors.extend(val_errors)

    return len(errors) == 0, errors


async def publish_record(
    db: AsyncSession,
    record_type: str,
    record_id: str,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Publish a record after validation. Returns result dict."""
    ok, errors = await can_publish(db, record_type, record_id)
    if not ok:
        return {"ok": False, "errors": errors}

    model = MODEL_MAP[record_type]
    result = await db.execute(select(model).where(model.id == record_id))
    rec = cast(Object | Entity | Place | Occurrence | None, result.scalar_one_or_none())
    if rec is None:
        return {"ok": False, "errors": ["Datensatz nicht gefunden"]}

    rec.status = "public"
    await flush_record(db, rec)

    # Audit log
    try:
        await log_change(
            db,
            record_type=record_type,
            record_id=rec.id,
            user_id=__import__("uuid").UUID(user_id) if user_id else None,
            action="publish",
            changed_fields={"status": "public"},
        )
    except Exception:
        pass

    # Re-index in ES with new status
    try:
        await index_record(record_type, rec, db)
    except Exception:
        pass

    return {"ok": True, "record_id": str(rec.id), "status": "public"}
