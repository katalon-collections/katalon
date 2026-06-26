from __future__ import annotations

import asyncio
from typing import Any

from katalon.workers.celery_app import celery_app


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


async def _do_cleanup(session: Any, deleted_type: str, deleted_id: str) -> dict:
    """Remove dangling {id: deleted_id} entries from metadata_ JSONB across primary types.

    Factored out of the Celery task for testability.
    """
    from sqlalchemy import select

    from katalon.core.models import Entity, FieldDefinition, Object, Occurrence, Place, Procedure

    MODEL_MAP: dict[str, Any] = {
        "object": Object,
        "entity": Entity,
        "place": Place,
        "occurrence": Occurrence,
        "procedure": Procedure,
    }

    fd_result = await session.execute(
        select(FieldDefinition).where(
            FieldDefinition.field_type == "relation",
            FieldDefinition.is_deleted.is_(False),
        )
    )
    all_relation_fields = fd_result.scalars().all()

    # Build map: record_type → field names that reference deleted_type
    fields_by_record_type: dict[str, list[str]] = {}
    for fd in all_relation_fields:
        if fd.settings.get("target_type") == deleted_type:
            fields_by_record_type.setdefault(fd.target_type, []).append(fd.name)

    cleaned = 0
    for record_type, field_names in fields_by_record_type.items():
        model = MODEL_MAP.get(record_type)
        if model is None:
            continue
        records = (await session.execute(select(model))).scalars().all()
        for record in records:
            new_meta = dict(record.metadata_)
            modified = False
            for field_name in field_names:
                val = new_meta.get(field_name)
                if val is None:
                    continue
                if isinstance(val, list):
                    filtered = [
                        v for v in val
                        if not (isinstance(v, dict) and v.get("id") == deleted_id)
                    ]
                    if len(filtered) != len(val):
                        new_meta[field_name] = filtered
                        modified = True
                elif isinstance(val, dict) and val.get("id") == deleted_id:
                    new_meta[field_name] = None
                    modified = True
            if modified:
                record.metadata_ = new_meta
                cleaned += 1

    return {"status": "ok", "cleaned": cleaned, "deleted_type": deleted_type, "deleted_id": deleted_id}


@celery_app.task(name="katalon.cleanup_relation_refs")
def cleanup_relation_refs(deleted_type: str, deleted_id: str) -> dict:
    """Remove dangling relation-field entries from metadata_ JSONB in primary type tables."""
    from katalon.database import AsyncSessionLocal

    async def _run_cleanup() -> dict:
        async with AsyncSessionLocal() as session:
            result = await _do_cleanup(session, deleted_type, deleted_id)
            await session.commit()
            return result

    return _run(_run_cleanup())
