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


@celery_app.task(name="katalon.reindex_all")
def reindex_all_task() -> None:
    """Full reindex – reads all records from DB and pushes to ES."""
    from katalon.database import AsyncSessionLocal
    from katalon.core.models import Object, Entity, Place, Occurrence
    from katalon.integrations.elasticsearch import ensure_index, index_document

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
                records = result.scalars().all()
                for rec in records:
                    title = ""
                    metadata: dict = {}
                    if getattr(rec, "metadata", None):
                        md = rec.metadata
                        title_field = md.get("title") or md.get("name") or md.get("label")
                        if isinstance(title_field, list) and title_field:
                            first = title_field[0]
                            title = first.get("value", "") if isinstance(first, dict) else str(first)
                        elif isinstance(title_field, str):
                            title = title_field
                        metadata = md
                    doc = {
                        "record_type": rtype,
                        "title": title,
                        "status": getattr(rec, "status", None),
                        "metadata": metadata,
                        "created_at": rec.created_at.isoformat() if rec.created_at else None,
                        "updated_at": rec.updated_at.isoformat() if rec.updated_at else None,
                    }
                    await index_document(str(rec.id), doc)

    _run(_reindex())
