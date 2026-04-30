from __future__ import annotations

import asyncio
from typing import Any

from katalon.workers.celery_app import celery_app


def _run(coro: Any) -> Any:
    return asyncio.get_event_loop().run_until_complete(coro)


@celery_app.task(name="katalon.import_records", bind=True)
def import_records_task(
    self,
    record_type: str,
    rows: list[dict[str, str]],
    mapping: dict[str, str],
) -> dict[str, Any]:
    from katalon.services.importer_service import apply_mapping
    from katalon.database import AsyncSessionLocal
    from katalon.core.models import KatalonObject, Entity, Occurrence

    model_map = {
        "object": KatalonObject,
        "entity": Entity,
        "occurrence": Occurrence,
    }
    model = model_map.get(record_type)
    if model is None:
        return {"error": f"Unknown record_type: {record_type}"}

    records = apply_mapping(rows, mapping)
    created = 0
    errors: list[dict] = []

    async def _import() -> None:
        nonlocal created
        async with AsyncSessionLocal() as session:
            for i, metadata in enumerate(records):
                try:
                    rec = model(metadata_=metadata, status="draft")
                    session.add(rec)
                    created += 1
                except Exception as exc:
                    errors.append({"row": i + 1, "error": str(exc)})
            await session.commit()

    _run(_import())
    return {"created": created, "errors": errors}
