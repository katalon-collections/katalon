from __future__ import annotations

import asyncio
from typing import Any

from katalon.workers.celery_app import celery_app


def _run(coro: Any) -> Any:
    """Run a coroutine in a fresh event loop."""
    return asyncio.run(coro)


@celery_app.task(name="katalon.index_record")
def index_record_task(record_type: str, record_id: str, doc: dict) -> None:
    from katalon.integrations.elasticsearch import index_document

    _run(index_document(record_id, {"record_type": record_type, **doc}))


@celery_app.task(name="katalon.remove_record")
def remove_record_task(record_id: str) -> None:
    from katalon.integrations.elasticsearch import delete_document

    _run(delete_document(record_id))


def _make_session():
    """Create a fresh async session with NullPool to avoid event-loop binding issues."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from katalon.config import settings

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False), engine


@celery_app.task(name="katalon.bulk_reindex_type")
def bulk_reindex_type_task(target_type: str) -> dict:
    """Reindex all records of a single type (e.g. after schema changes)."""
    from sqlalchemy import select

    from katalon.core.models import Entity, Object, Occurrence, Place
    from katalon.integrations.elasticsearch import reindex_type
    from katalon.services.search_service import _build_doc

    _MODEL_MAP: dict = {
        "object": Object,
        "entity": Entity,
        "place": Place,
        "occurrence": Occurrence,
    }

    AsyncSessionLocal, engine = _make_session()

    async def _do() -> dict:
        from katalon.core.models import FieldDefinition
        from katalon.services.search_service import _load_relation_titles

        model = _MODEL_MAP.get(target_type)
        if model is None:
            return {"status": "error", "detail": f"Unknown type: {target_type}"}
        async with AsyncSessionLocal() as session:
            # Load facet fields for this type
            fd_result = await session.execute(
                select(FieldDefinition.name).where(
                    FieldDefinition.target_type == target_type,
                    FieldDefinition.is_facet.is_(True),
                    FieldDefinition.is_deleted.is_(False),
                )
            )
            facet_fields = set(fd_result.scalars().all())

            result = await session.execute(select(model))
            records = []
            for rec in result.scalars().all():
                rel_data = None
                if target_type == "object":
                    rel_data = await _load_relation_titles(target_type, rec.id, session)
                records.append((str(rec.id), _build_doc(target_type, rec, rel_data, facet_fields=facet_fields)))
        count = await reindex_type(target_type, records)
        return {"status": "ok", "indexed": count, "target_type": target_type}

    try:
        return _run(_do())
    finally:
        _run(engine.dispose())


@celery_app.task(name="katalon.reindex_all")
def reindex_all_task() -> None:
    """Full reindex – reads all records from DB and pushes to ES."""
    from katalon.core.models import Entity, Object, Occurrence, Place
    from katalon.integrations.elasticsearch import ensure_index
    from katalon.services.search_service import index_record as _index

    AsyncSessionLocal, engine = _make_session()

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
                    await _index(rtype, rec, session)

    try:
        _run(_reindex())
    finally:
        _run(engine.dispose())
