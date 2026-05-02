from __future__ import annotations

import asyncio
from typing import Any

from katalon.workers.celery_app import celery_app


def _run(coro: Any) -> Any:
    return asyncio.get_event_loop().run_until_complete(coro)


@celery_app.task(name="katalon.index_record")
def index_record_task(record_type: str, record_id: str, doc: dict) -> None:
    from katalon.integrations.elasticsearch import index_document

    _run(index_document(record_id, {"record_type": record_type, **doc}))


@celery_app.task(name="katalon.remove_record")
def remove_record_task(record_id: str) -> None:
    from katalon.integrations.elasticsearch import delete_document

    _run(delete_document(record_id))


@celery_app.task(name="katalon.bulk_reindex_type")
def bulk_reindex_type_task(target_type: str) -> dict:
    """Reindex all records of a single type (e.g. after schema changes)."""
    from katalon.database import AsyncSessionLocal
    from katalon.core.models import Object, Entity, Place, Occurrence
    from katalon.services.search_service import _build_doc
    from katalon.integrations.elasticsearch import reindex_type
    from sqlalchemy import select

    _MODEL_MAP: dict = {
        "object": Object,
        "entity": Entity,
        "place": Place,
        "occurrence": Occurrence,
    }

    async def _do() -> dict:
        model = _MODEL_MAP.get(target_type)
        if model is None:
            return {"status": "error", "detail": f"Unknown type: {target_type}"}
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(model))
            records = [
                (str(rec.id), _build_doc(target_type, rec))
                for rec in result.scalars().all()
            ]
        count = await reindex_type(target_type, records)
        return {"status": "ok", "indexed": count, "target_type": target_type}

    return _run(_do())


@celery_app.task(name="katalon.reindex_all")
def reindex_all_task() -> None:
    """Full reindex – reads all records from DB and pushes to ES."""
    from katalon.database import AsyncSessionLocal
    from katalon.core.models import Object, Entity, Place, Occurrence
    from katalon.integrations.elasticsearch import ensure_index
    from katalon.services.search_service import _build_doc, index_record as _index

    async def _reindex() -> None:
        from sqlalchemy import select

        await ensure_index()
        async with AsyncSessionLocal() as session:
            for model, rtype in [
                (Object, "object"),
                (Entity, "entity"),
                (Place, "place"),
                (Occurrence, "occurrence"),
            ]:
                result = await session.execute(select(model))
                for rec in result.scalars().all():
                    await _index(rtype, rec)

    _run(_reindex())
