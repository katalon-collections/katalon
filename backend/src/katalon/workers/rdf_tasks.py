# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from katalon.config import settings
from katalon.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run[T](coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine in a fresh event loop."""
    return asyncio.run(coro)


def _make_session() -> tuple[async_sessionmaker[AsyncSession], AsyncEngine]:
    """Create a fresh async session with NullPool to avoid event-loop binding issues."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False), engine


@celery_app.task(
    name="katalon.sync_rdf_record",
    bind=True,
    max_retries=3,
)
def sync_rdf_record_task(self: Any, record_type: str, record_id: str) -> dict[str, Any]:
    """Synchronize a record's named graph to Oxigraph.

    Short-circuits immediately if settings.oxigraph_enabled is False.
    """
    if not settings.oxigraph_enabled:
        return {"status": "skipped", "reason": "disabled"}

    from katalon.services.rdf_sync_service import sync_record_to_oxigraph

    AsyncSessionLocal, engine = _make_session()

    async def _do_sync() -> dict[str, Any]:
        async with AsyncSessionLocal() as session:
            return await sync_record_to_oxigraph(record_type, record_id, session)

    try:
        return _run(_do_sync())
    except Exception as exc:
        logger.error(
            "sync_rdf_record failed %s/%s (attempt %d): %s",
            record_type,
            record_id,
            self.request.retries + 1,
            exc,
        )
        try:
            raise self.retry(exc=exc, countdown=5 * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            logger.error(
                "sync_rdf_record permanently failed %s/%s after %d retries",
                record_type,
                record_id,
                self.max_retries,
            )
            return {"status": "error", "error": str(exc)}
    finally:
        _run(engine.dispose())


@celery_app.task(
    name="katalon.remove_rdf_record",
    bind=True,
    max_retries=3,
)
def remove_rdf_record_task(
    self: Any, record_type: str | None, record_id: str
) -> dict[str, Any]:
    """Remove a record's named graph from Oxigraph.

    Short-circuits immediately if settings.oxigraph_enabled is False.
    If record_type is None, attempts removal across all primary record types.
    """
    if not settings.oxigraph_enabled:
        return {"status": "skipped", "reason": "disabled"}

    from katalon.services.rdf_service import RECORD_MODEL_MAP
    from katalon.services.rdf_sync_service import remove_record_from_oxigraph

    types_to_remove = [record_type] if record_type else list(RECORD_MODEL_MAP.keys())

    async def _do_remove() -> dict[str, Any]:
        results = [await remove_record_from_oxigraph(rtype, record_id) for rtype in types_to_remove]
        return {"status": "deleted", "record_id": record_id, "results": results}
    try:
        return _run(_do_remove())
    except Exception as exc:
        logger.error(
            "remove_rdf_record failed %s/%s (attempt %d): %s",
            record_type,
            record_id,
            self.request.retries + 1,
            exc,
        )
        try:
            raise self.retry(exc=exc, countdown=5 * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            logger.error(
                "remove_rdf_record permanently failed %s/%s after %d retries",
                record_type,
                record_id,
                self.max_retries,
            )
            return {"status": "error", "error": str(exc)}


@celery_app.task(name="katalon.rebuild_rdf_all")
def rebuild_rdf_all_task() -> dict[str, Any]:
    """Rebuild the entire Oxigraph triple store from PostgreSQL for all published records."""
    if not settings.oxigraph_enabled:
        return {"status": "skipped", "reason": "disabled"}

    from katalon.services.rdf_sync_service import rebuild_all_oxigraph

    AsyncSessionLocal, engine = _make_session()

    async def _do_rebuild() -> dict[str, Any]:
        async with AsyncSessionLocal() as session:
            return await rebuild_all_oxigraph(session)

    try:
        return _run(_do_rebuild())
    finally:
        _run(engine.dispose())
