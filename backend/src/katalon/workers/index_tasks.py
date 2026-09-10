# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine, Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from katalon.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run[T](coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine in a fresh event loop."""
    return asyncio.run(coro)


def _make_session() -> tuple[async_sessionmaker[AsyncSession], AsyncEngine]:
    """Create a fresh async session with NullPool to avoid event-loop binding issues."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from katalon.config import settings

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False), engine


def _log_index_failure(record_type: str, record_id: str, error: str) -> None:
    """Write a permanent index failure to audit_log."""
    import uuid as _uuid_mod

    from katalon.core.models import AuditLog

    AsyncSessionLocal, engine = _make_session()

    async def _write() -> None:
        async with AsyncSessionLocal() as session:
            entry = AuditLog(
                record_type=record_type,
                record_id=_uuid_mod.UUID(record_id),
                user_id=None,
                action="index_failed",
                changed_fields={"error": error},
            )
            session.add(entry)
            await session.commit()

    try:
        _run(_write())
    except Exception:
        logger.exception(
            "Failed to write index_failed audit entry for %s/%s", record_type, record_id
        )
    finally:
        _run(engine.dispose())


@celery_app.task(
    name="katalon.index_record",
    bind=True,
    max_retries=3,
)
def index_record_task(self: Any, record_type: str, record_id: str, doc: dict[str, Any]) -> None:
    from katalon.integrations.elasticsearch import index_document

    try:
        _run(index_document(record_id, {"record_type": record_type, **doc}))
        cascade_reindex_task.delay(record_type, record_id)
    except Exception as exc:
        logger.error(
            "index_record failed %s/%s (attempt %d): %s",
            record_type,
            record_id,
            self.request.retries + 1,
            exc,
        )
        try:
            raise self.retry(exc=exc, countdown=10 * (2**self.request.retries))
        except self.MaxRetriesExceededError:
            logger.error(
                "index_record permanently failed %s/%s after %d retries",
                record_type,
                record_id,
                self.max_retries,
            )
            _log_index_failure(record_type, record_id, str(exc))


@celery_app.task(name="katalon.remove_record", bind=True, max_retries=3)
def remove_record_task(self: Any, record_id: str) -> None:
    from katalon.integrations.elasticsearch import delete_document

    try:
        _run(delete_document(record_id))
    except Exception as exc:
        logger.error(
            "remove_record failed %s (attempt %d): %s",
            record_id,
            self.request.retries + 1,
            exc,
        )
        try:
            raise self.retry(exc=exc, countdown=10 * (2**self.request.retries))
        except self.MaxRetriesExceededError:
            logger.error(
                "remove_record permanently failed %s after %d retries", record_id, self.max_retries
            )


@celery_app.task(name="katalon.cascade_reindex")
def cascade_reindex_task(record_type: str, record_id: str) -> dict[str, Any]:
    """Reindex all records linking TO the given record (1-level cascade).

    Triggered after index_record_task succeeds. Propagates inherited field
    changes to records that embed data from this record. Max depth: 1.
    """
    from sqlalchemy import and_, select

    from katalon.core.models import Entity, Object, Occurrence, Place, Procedure, Relation
    from katalon.integrations.elasticsearch import index_document
    from katalon.services.search_service import build_index_doc

    _MODEL_MAP: dict[str, Any] = {
        "object": Object,
        "entity": Entity,
        "place": Place,
        "occurrence": Occurrence,
        "procedure": Procedure,
    }

    AsyncSessionLocal, engine = _make_session()

    async def _do() -> dict[str, Any]:
        async with AsyncSessionLocal() as session:
            stmt = select(Relation).where(
                and_(Relation.to_type == record_type, Relation.to_id == record_id)
            )
            relations = (await session.execute(stmt)).scalars().all()
            count = 0
            for rel in relations:
                model = _MODEL_MAP.get(rel.from_type)
                if not model:
                    continue
                rec = await session.get(model, rel.from_id)
                if not rec:
                    continue
                doc = await build_index_doc(rel.from_type, rec, session)
                await index_document(str(rec.id), {"record_type": rel.from_type, **doc})
                count += 1
        return {"cascaded": count, "source": f"{record_type}/{record_id}"}

    try:
        return _run(_do())
    finally:
        _run(engine.dispose())


@celery_app.task(name="katalon.bulk_reindex_type")
def bulk_reindex_type_task(target_type: str) -> dict[str, Any]:
    """Reindex all records of a single type (e.g. after schema changes)."""
    import redis as redis_lib
    from sqlalchemy import select

    from katalon.config import settings
    from katalon.core.models import (
        Collection,
        Entity,
        Object,
        Occurrence,
        Place,
        Procedure,
        StorageLocation,
    )
    from katalon.integrations.elasticsearch import reindex_type
    from katalon.services.search_service import build_index_doc

    _MODEL_MAP: dict[str, Any] = {
        "object": Object,
        "entity": Entity,
        "place": Place,
        "occurrence": Occurrence,
        "procedure": Procedure,
        "collection": Collection,
        "storage_location": StorageLocation,
    }

    AsyncSessionLocal, engine = _make_session()

    # Build docs concurrently in worker chunks: each chunk keeps ONE session
    # (NullPool connection) for its whole share, so the per-record N+1 queries
    # (relations, media, export context) interleave across chunks instead of
    # serialising — without per-record connection setup. 31k objects took
    # ~30 min sequentially; the chunked run finishes in a few minutes.
    build_concurrency = 16

    async def _do() -> dict[str, Any]:
        model = _MODEL_MAP.get(target_type)
        if model is None:
            return {"status": "error", "detail": f"Unknown type: {target_type}"}
        async with AsyncSessionLocal() as session:
            query = select(model)
            if hasattr(model, "deleted_at"):
                query = query.where(model.deleted_at.is_(None))
            result = await session.execute(query)
            records = result.scalars().all()

        total = len(records)
        logger.info(
            "bulk_reindex_type_task: building %d index docs for '%s' (concurrency=%d)",
            total,
            target_type,
            build_concurrency,
        )

        chunks = [records[i::build_concurrency] for i in range(build_concurrency)]
        done = 0

        async def _build_chunk(chunk: Sequence[Any]) -> list[tuple[str, dict[str, Any]]]:
            nonlocal done
            built: list[tuple[str, dict[str, Any]]] = []
            async with AsyncSessionLocal() as session:
                for rec in chunk:
                    doc = await build_index_doc(target_type, rec, session)
                    built.append((str(rec.id), doc))
                    done += 1
                    if done % 2000 == 0 or done == total:
                        logger.info(
                            "bulk_reindex_type_task: %d/%d docs built for '%s'",
                            done,
                            total,
                            target_type,
                        )
            return built

        results = await asyncio.gather(*(_build_chunk(c) for c in chunks if c))
        docs = [item for chunk in results for item in chunk]
        count = await reindex_type(target_type, docs)
        logger.info(
            "bulk_reindex_type_task: successfully indexed %d records for '%s'", count, target_type
        )
        return {"status": "ok", "indexed": count, "target_type": target_type}

    redis_client = redis_lib.from_url(settings.redis_url)  # type: ignore[no-untyped-call]
    try:
        # ponytail: 1h lease; add renewal if one type can take longer to rebuild.
        with redis_client.lock(
            f"katalon:reindex:{target_type}", timeout=3600, blocking_timeout=3600
        ):
            return _run(_do())
    finally:
        redis_client.close()
        _run(engine.dispose())


@celery_app.task(name="katalon.reconciliation_job")
def reconciliation_job_task(mode: str = "count", force: bool = False) -> dict[str, Any]:
    """Layer 3 safety net (#214): compare DB vs. ES counts and self-heal.

    mode="count": fast DB-vs-ES count comparison; if the delta exceeds the
    configured threshold, falls through to an ID-diff for that type.
    mode="id_diff": always determines concrete missing IDs and reindexes them.

    `force=True` (manual trigger) bypasses the `reconciliation_enabled` toggle —
    that toggle only governs the scheduled background runs.
    """
    from sqlalchemy import func, select, true

    from katalon.core.models import AdminConfig, Entity, Object, Occurrence, Place, Procedure
    from katalon.integrations.elasticsearch import count_by_type, list_ids_by_type

    _MODEL_MAP: dict[str, Any] = {
        "object": Object,
        "entity": Entity,
        "place": Place,
        "occurrence": Occurrence,
        "procedure": Procedure,
    }

    AsyncSessionLocal, engine = _make_session()

    async def _do() -> dict[str, Any]:
        async with AsyncSessionLocal() as session:
            cfg_stmt = select(AdminConfig).where(AdminConfig.key == "default")
            config = (await session.execute(cfg_stmt)).scalar_one_or_none()
            if config and not config.reconciliation_enabled and not force:
                return {"status": "skipped", "reason": "reconciliation_disabled"}
            threshold = config.reconciliation_threshold if config else 5
            id_diff_enabled = config.reconciliation_id_diff_enabled if config else True

            report: dict[str, dict[str, Any]] = {}
            for record_type, model in _MODEL_MAP.items():
                not_deleted = model.deleted_at.is_(None) if hasattr(model, "deleted_at") else true()
                count_stmt = select(func.count()).select_from(model).where(not_deleted)
                db_count = (await session.execute(count_stmt)).scalar_one()
                es_count = await count_by_type(record_type)
                delta = db_count - es_count
                entry: dict[str, Any] = {
                    "db": db_count,
                    "es": es_count,
                    "delta": delta,
                    "reindexed": 0,
                }

                run_id_diff = id_diff_enabled and (mode == "id_diff" or abs(delta) > threshold)
                if run_id_diff:
                    db_ids = set(
                        str(r[0])
                        for r in (await session.execute(select(model.id).where(not_deleted))).all()
                    )
                    es_ids = await list_ids_by_type(record_type)
                    missing = db_ids - es_ids
                    stale = es_ids - db_ids
                    for record_id in missing:
                        index_record_dispatch_task.delay(record_type, record_id)
                    for stale_id in stale:
                        remove_record_task.delay(stale_id)
                    entry["reindexed"] = len(missing)
                    entry["removed"] = len(stale)
                    entry["mode"] = "id_diff"
                else:
                    entry["mode"] = "count"
                report[record_type] = entry
        return report

    try:
        return _run(_do())
    finally:
        _run(engine.dispose())


@celery_app.task(name="katalon.index_record_dispatch")
def index_record_dispatch_task(record_type: str, record_id: str) -> None:
    """Build index doc for one record and dispatch indexing (used by reconciliation)."""
    import uuid as _uuid_mod

    from katalon.core.models import Entity, Object, Occurrence, Place, Procedure
    from katalon.services.search_service import build_index_doc

    _MODEL_MAP: dict[str, Any] = {
        "object": Object,
        "entity": Entity,
        "place": Place,
        "occurrence": Occurrence,
        "procedure": Procedure,
    }
    model = _MODEL_MAP.get(record_type)
    if model is None:
        return

    AsyncSessionLocal, engine = _make_session()

    async def _do() -> dict[str, Any] | None:
        async with AsyncSessionLocal() as session:
            rec = await session.get(model, _uuid_mod.UUID(record_id))
            if not rec:
                return None
            return await build_index_doc(record_type, rec, session)

    try:
        doc = _run(_do())
    finally:
        _run(engine.dispose())

    if doc is not None:
        index_record_task.delay(record_type, record_id, doc)


@celery_app.task(name="katalon.reindex_all")
def reindex_all_task() -> dict[str, Any]:
    """Full reindex – rebuild every indexed record type via the chunked builder.

    Delegates to bulk_reindex_type_task per type (called inline, not delayed) so
    the full rebuild gets the same chunked concurrency and per-type Redis lock
    as a single-type rebuild.
    """
    results: dict[str, Any] = {}
    type_errors: list[str] = []
    for rtype in (
        "object",
        "entity",
        "place",
        "occurrence",
        "procedure",
        "collection",
        "storage_location",
    ):
        try:
            results[rtype] = bulk_reindex_type_task(rtype)
        except Exception as exc:
            logger.exception("reindex_all_task: failed to reindex type '%s': %s", rtype, exc)
            type_errors.append(f"{rtype}: {exc}")
    if type_errors:
        raise RuntimeError(f"reindex_all_task completed with errors: {'; '.join(type_errors)}")
    return {"status": "ok", "types": results}
