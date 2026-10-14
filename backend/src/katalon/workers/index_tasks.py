# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine, Sequence
from typing import Any

from celery.signals import worker_ready, worker_shutdown
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from katalon.config import settings
from katalon.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _record_models() -> dict[str, type[Any]]:
    """Models indexed under each supported core record type."""
    from katalon.core.models import (
        Collection,
        Entity,
        Object,
        Occurrence,
        Place,
        Procedure,
        StorageLocation,
    )

    return {
        "object": Object,
        "entity": Entity,
        "place": Place,
        "occurrence": Occurrence,
        "procedure": Procedure,
        "collection": Collection,
        "storage_location": StorageLocation,
    }


def _run[T](coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine in a fresh event loop and close that loop's ES client."""

    async def _with_cleanup() -> T:
        from katalon.integrations.elasticsearch import close_es

        try:
            return await coro
        finally:
            await close_es()

    return asyncio.run(_with_cleanup())


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
    """Reindex records linked in either direction (1-level cascade).

    Triggered after index_record_task succeeds. Propagates inherited field
    changes to records that embed data from this record. Max depth: 1.
    """
    from sqlalchemy import and_, or_, select

    from katalon.core.models import Relation
    from katalon.integrations.elasticsearch import index_document
    from katalon.services.search_service import build_index_doc

    model_map = _record_models()

    AsyncSessionLocal, engine = _make_session()

    async def _do() -> dict[str, Any]:
        async with AsyncSessionLocal() as session:
            stmt = select(Relation).where(
                or_(
                    and_(Relation.to_type == record_type, Relation.to_id == record_id),
                    and_(Relation.from_type == record_type, Relation.from_id == record_id),
                )
            )
            relations = (await session.execute(stmt)).scalars().all()
            count = 0
            seen: set[tuple[str, Any]] = {(record_type, record_id)}
            for rel in relations:
                if rel.from_type == record_type and str(rel.from_id) == str(record_id):
                    other_type, other_id = rel.to_type, rel.to_id
                else:
                    other_type, other_id = rel.from_type, rel.from_id
                key = (other_type, str(other_id))
                if key in seen:
                    continue
                seen.add(key)
                model = model_map.get(other_type)
                if not model:
                    continue
                rec = await session.get(model, other_id)
                if not rec or getattr(rec, "deleted_at", None) is not None:
                    continue
                doc = await build_index_doc(other_type, rec, session)
                await index_document(str(rec.id), {"record_type": other_type, **doc})
                count += 1
        return {"cascaded": count, "source": f"{record_type}/{record_id}"}

    try:
        return _run(_do())
    finally:
        _run(engine.dispose())


# Records are built in batches of this size (settings.es_reindex_batch_size);
# only one batch is held in memory at a time (the previous build-everything-
# then-send approach peaked at several GB of worker RSS for ~32k objects).
# Sending is additionally split by bytes (settings.es_bulk_max_bytes).
REINDEX_BATCH_SIZE = settings.es_reindex_batch_size
# Concurrent build sessions within a batch: each keeps ONE NullPool connection
# for the whole run, so the per-record N+1 queries (relations, media, export
# context) interleave instead of serialising, without per-record connect cost.
REINDEX_BUILD_CONCURRENCY = 16


# acks_late=False: Redis redelivers unacked messages after its visibility
# timeout (1 h). A rebuild running longer than that would be delivered a second
# time while still running. Crash recovery instead comes from the dirty marker,
# which is only cleared after a successful run (see _resubmit_pending_reindexes).
@celery_app.task(name="katalon.bulk_reindex_type", bind=True, acks_late=False)
def bulk_reindex_type_task(self: Any, target_type: str, coalesce: bool = False) -> dict[str, Any]:
    """Rebuild all ES documents of one record type from current DB state.

    ``coalesce=True`` marks a job enqueued via ``request_bulk_reindex``: it
    skips when no change is pending. Rebuilds run one at a time; a job never
    blocks waiting for the run lock — it returns ``deferred`` and the running
    job resubmits it when it ends (see workers/reindex_state.py).
    """
    from katalon.workers import reindex_state

    client = reindex_state.redis_client()
    try:
        if coalesce:
            client.delete(reindex_state.queued_key(target_type))
        lock = reindex_state.run_lock(client)
        if not lock.acquire(blocking=False):
            if not coalesce:
                # A direct call (manual/reindex_all/legacy message) has no
                # dirty mark from request_bulk_reindex — leave one so the
                # running job follows up.
                reindex_state.mark_dirty(client, target_type)
            logger.info("bulk_reindex_type_task: a rebuild is running — '%s' deferred", target_type)
            return {"status": "deferred", "target_type": target_type}

        reindex_state.register_held_lock(lock)
        succeeded = False
        try:
            # Read, don't consume: the marker stays until this run succeeded,
            # so a crashed run is picked up again on the next worker start.
            dirty_token = client.get(reindex_state.dirty_key(target_type))
            if coalesce and not dirty_token:
                return {"status": "skipped", "target_type": target_type}
            task_id = getattr(getattr(self, "request", None), "id", None)
            progress = reindex_state.ProgressReporter(client, target_type, task_id)
            try:
                with reindex_state.LeaseWatchdog(lock):
                    report = _run(_stream_reindex(target_type, progress))
            except Exception as exc:
                progress.finish("failed", error=str(exc)[:1000])
                raise
            progress.finish(
                report["status"] if report["status"] != "ok" else "done",
                indexed=report.get("indexed", 0),
                removed=report.get("removed", 0),
            )
            succeeded = True
            if dirty_token:
                # Clears the marker only if no request arrived during the run.
                reindex_state.clear_dirty_if_unchanged(client, target_type, dirty_token)
            return report
        finally:
            reindex_state.unregister_held_lock(lock)
            try:
                lock.release()
            except Exception:
                logger.warning("reindex lock for '%s' already expired", target_type)
            # Follow up only after success; a failing rebuild must not loop.
            # Covers this type's changes during the run and every rebuild that
            # was deferred while the run lock was held.
            if succeeded:
                reindex_state.resubmit_pending(list(_record_models()))
    finally:
        client.close()
        # Return freed batch memory to the allocator before the thread idles.
        import gc

        gc.collect()


async def _stream_reindex(
    target_type: str,
    progress: Any,
    *,
    index: str | None = None,
    ids: list[Any] | None = None,
    sweep_stale: bool = True,
) -> dict[str, Any]:
    """Build and send docs batch by batch; afterwards drop docs of records that
    no longer exist (or are soft-deleted). Never deletes the whole type first,
    so the portal keeps the previous state of every record during the run.

    ``index`` defaults to the live alias; the full rebuild passes its new
    physical index, explicit ``ids`` (catch-up pass) and ``sweep_stale=False``.
    """
    import contextlib
    import itertools

    from sqlalchemy import select

    from katalon.integrations.elasticsearch import (
        INDEX_NAME,
        ReindexBatchError,
        bulk_index_documents,
        delete_documents,
        get_es,
        list_ids_by_type,
    )
    from katalon.services.search_service import build_index_doc

    model = _record_models().get(target_type)
    if model is None:
        return {"status": "error", "detail": f"Unknown type: {target_type}"}
    not_deleted = model.deleted_at.is_(None) if hasattr(model, "deleted_at") else None

    target_index = index or INDEX_NAME
    session_factory, engine = _make_session()
    es = get_es()
    if index is None:
        # Never let the first bulk write auto-create the live index with a
        # purely dynamic mapping (worker running before the API ever started).
        from katalon.integrations.elasticsearch import ensure_index

        await ensure_index()
    try:
        if ids is None:
            async with session_factory() as session:
                id_query = select(model.id).order_by(model.id)
                if not_deleted is not None:
                    id_query = id_query.where(not_deleted)
                ids = list((await session.execute(id_query)).scalars().all())

        total = len(ids)
        progress.update(force=True, total=total)
        logger.info(
            "bulk_reindex_type_task: streaming %d docs for '%s' (batch=%d, concurrency=%d)",
            total,
            target_type,
            REINDEX_BATCH_SIZE,
            REINDEX_BUILD_CONCURRENCY,
        )

        built = indexed = 0
        failed: list[str] = []
        seen: set[str] = set()
        async with contextlib.AsyncExitStack() as stack:
            sessions = [
                await stack.enter_async_context(session_factory())
                for _ in range(min(REINDEX_BUILD_CONCURRENCY, max(total, 1)))
            ]

            async def _build(session: Any, part: Sequence[Any]) -> list[tuple[str, dict[str, Any]]]:
                query = select(model).where(model.id.in_(part))
                if not_deleted is not None:
                    query = query.where(not_deleted)
                records = (await session.execute(query)).scalars().all()
                out = [
                    (str(rec.id), await build_index_doc(target_type, rec, session))
                    for rec in records
                ]
                # Drop this batch's ORM state (records, relations, media) so the
                # identity map does not grow across the whole run.
                session.expunge_all()
                return out

            for batch in itertools.batched(ids, REINDEX_BATCH_SIZE, strict=False):
                parts = [batch[i :: len(sessions)] for i in range(len(sessions))]
                results = await asyncio.gather(
                    *(_build(s, p) for s, p in zip(sessions, parts, strict=True) if p)
                )
                docs = [doc for part in results for doc in part]
                built += len(docs)
                ok, batch_failed = await bulk_index_documents(
                    es, target_type, docs, index=target_index
                )
                indexed += ok
                failed.extend(batch_failed)
                seen.update(doc_id for doc_id, _ in docs)
                del docs, results
                progress.update(built=built, indexed=indexed)
                if built % 2000 < REINDEX_BATCH_SIZE or built == total:
                    logger.info(
                        "bulk_reindex_type_task: %d/%d docs for '%s'", built, total, target_type
                    )

        # Stale docs: in ES but not built in this run. A record created (and
        # indexed individually) after the id snapshot is not stale — recheck
        # candidates against the DB before deleting.
        stale = (await list_ids_by_type(target_type)) - seen if sweep_stale else set()
        removed = 0
        if stale:
            import uuid as _uuid_mod

            stale_uuids = []
            for raw in stale:
                with contextlib.suppress(ValueError):
                    stale_uuids.append(_uuid_mod.UUID(raw))
            alive: set[str] = set()
            async with session_factory() as session:
                for chunk in itertools.batched(stale_uuids, 1000, strict=False):
                    alive_query = select(model.id).where(model.id.in_(chunk))
                    if not_deleted is not None:
                        alive_query = alive_query.where(not_deleted)
                    alive.update(str(i) for i in (await session.execute(alive_query)).scalars())
            removed = await delete_documents(es, stale - alive)
        progress.update(force=True, built=built, indexed=indexed, removed=removed)

        await es.indices.refresh(index=target_index)
        logger.info(
            "bulk_reindex_type_task: indexed %d, removed %d stale for '%s'",
            indexed,
            removed,
            target_type,
        )
        if failed:
            raise ReindexBatchError(
                f"Reindex for '{target_type}': {len(failed)} document(s) failed to index "
                f"(e.g. {failed[:5]}); {indexed} indexed.",
                target_type=target_type,
                failed_batches=[{"doc_ids": failed}],
                indexed_count=indexed,
            )
        return {
            "status": "ok",
            "indexed": indexed,
            "removed": removed,
            "target_type": target_type,
        }
    finally:
        await engine.dispose()


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

    from katalon.core.models import AdminConfig
    from katalon.integrations.elasticsearch import count_by_type, list_ids_by_type

    model_map = _record_models()

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
            for record_type, model in model_map.items():
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

    from katalon.services.search_service import build_index_doc

    model = _record_models().get(record_type)
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


@celery_app.task(name="katalon.reindex_all", bind=True, acks_late=False)
def reindex_all_task(self: Any, coalesce: bool = False) -> dict[str, Any]:
    """Full rebuild into a fresh physical index, then switch the alias.

    Unlike the in-place type rebuild this also replaces the index mapping
    (e.g. after a dynamically mapped field got the wrong type). The live index
    keeps serving until the atomic alias switch; single-document writes during
    the build also go to the new index, and a catch-up pass re-reads every
    record changed since the build started.
    """
    from katalon.workers import reindex_state

    full = reindex_state.FULL
    client = reindex_state.redis_client()
    try:
        if coalesce:
            client.delete(reindex_state.queued_key(full))
        lock = reindex_state.run_lock(client)
        if not lock.acquire(blocking=False):
            if not coalesce:
                reindex_state.mark_dirty(client, full)
            logger.info("reindex_all_task: a rebuild is running — deferred")
            return {"status": "deferred"}

        reindex_state.register_held_lock(lock)
        succeeded = False
        try:
            types = list(_record_models())
            tokens = {
                name: client.get(reindex_state.dirty_key(name)) for name in [full, *types]
            }
            if coalesce and not tokens[full]:
                return {"status": "skipped"}
            task_id = getattr(getattr(self, "request", None), "id", None)
            with reindex_state.LeaseWatchdog(lock):
                report = _run(_full_rebuild(client, types, task_id))
            succeeded = True
            # Everything requested before the build started is covered now.
            for name, token in tokens.items():
                if token:
                    reindex_state.clear_dirty_if_unchanged(client, name, token)
            return report
        finally:
            reindex_state.unregister_held_lock(lock)
            try:
                lock.release()
            except Exception:
                logger.warning("reindex run lock already expired")
            if succeeded:
                reindex_state.resubmit_pending(list(_record_models()))
    finally:
        client.close()
        import gc

        gc.collect()


class _NoProgress:
    def update(self, **_kwargs: Any) -> None:
        return None


async def _full_rebuild(client: Any, types: list[str], task_id: str | None) -> dict[str, Any]:
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from katalon.integrations.elasticsearch import (
        SHADOW_INDEX_KEY,
        create_physical_index,
        delete_documents,
        delete_physical_index,
        get_es,
        new_physical_index_name,
        swap_alias,
    )
    from katalon.workers import reindex_state

    # DB timestamps are naive UTC; the margin covers clock skew between hosts.
    started = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=5)
    new_index = new_physical_index_name()
    await create_physical_index(new_index)
    overall = reindex_state.ProgressReporter(client, reindex_state.FULL, task_id)
    client.set(SHADOW_INDEX_KEY, new_index, ex=reindex_state.DIRTY_TTL_SECONDS)
    results: dict[str, Any] = {}
    switch_started = False
    try:
        for done, target_type in enumerate(types):
            overall.update(force=True, total=len(types), built=done, current_type=target_type)
            progress = reindex_state.ProgressReporter(client, target_type, task_id)
            try:
                report = await _stream_reindex(
                    target_type, progress, index=new_index, sweep_stale=False
                )
            except Exception as exc:
                progress.finish("failed", error=str(exc)[:1000])
                raise
            progress.finish("done", indexed=report.get("indexed", 0), removed=0)
            results[target_type] = report

        # Catch-up: records changed while the build ran may have been read
        # before their change; re-read them. Shadow writes cover the rest.
        session_factory, engine = _make_session()
        try:
            for target_type, model in _record_models().items():
                changed: list[Any] = []
                gone: list[str] = []
                async with session_factory() as session:
                    if hasattr(model, "updated_at"):
                        query = select(model.id).where(model.updated_at >= started)
                        if hasattr(model, "deleted_at"):
                            query = query.where(model.deleted_at.is_(None))
                        changed = list((await session.execute(query)).scalars())
                    if hasattr(model, "deleted_at"):
                        deleted_query = select(model.id).where(model.deleted_at >= started)
                        gone = [str(i) for i in (await session.execute(deleted_query)).scalars()]
                if changed:
                    await _stream_reindex(
                        target_type, _NoProgress(), index=new_index, ids=changed, sweep_stale=False
                    )
                if gone:
                    await delete_documents(get_es(), gone, index=new_index)
                results[target_type]["caught_up"] = len(changed) + len(gone)
        finally:
            await engine.dispose()

        await get_es().indices.refresh(index=new_index)
        switch_started = True
        replaced = await swap_alias(new_index)
    except Exception as exc:
        overall.finish("failed", error=str(exc)[:1000])
        # A timed-out switch may already have succeeded on ES: retain its target.
        if not switch_started:
            await delete_physical_index(new_index)
        raise
    finally:
        client.delete(SHADOW_INDEX_KEY)
    overall.finish("done", built=len(types), indexed=sum(r.get("indexed", 0) for r in results.values()))
    logger.info("reindex_all_task: switched to %s, previous indices %s", new_index, replaced)
    return {"status": "ok", "index": new_index, "replaced": replaced, "types": results}


@worker_ready.connect
def _resubmit_pending_reindexes(**_kwargs: Any) -> None:
    """Re-request rebuilds that were pending or interrupted (worker crash,
    lost message) — their dirty marker survived. Coalesces like any request."""
    from katalon.workers import reindex_state

    try:
        reindex_state.resubmit_pending(list(_record_models()))
    except Exception:
        logger.warning("could not resubmit pending reindexes", exc_info=True)


@worker_shutdown.connect
def _release_reindex_locks(**_kwargs: Any) -> None:
    """Free reindex run locks on a deliberate worker stop instead of letting
    them block the type for the rest of their lease."""
    from katalon.workers import reindex_state

    reindex_state.release_all_held_locks()
