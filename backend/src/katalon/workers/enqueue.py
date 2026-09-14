# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Broker-tolerant Celery enqueue helpers.

Fire-and-forget background work (ES indexing/removal, RDF sync, relation
cleanup, tile generation, schema reindex) must never break the HTTP request
that triggered it, and must never let a worker observe a row before the
transaction that wrote it has actually committed (#392). Two separate
concerns, two helpers:

``after_commit(db, task, ...)`` — defer a call until ``db``'s current
transaction has committed. Use this whenever the task reads DB state this
same request/session just wrote (ES doc, RDF graph, relation cleanup): the
call is recorded on the session and only turned into a real ``enqueue()``
once ``katalon.database.get_db`` (or, for Celery-task-owned sessions, the
task itself — see ``run_after_commit_hooks``) observes a successful
``session.commit()``. A rollback discards it entirely — no ES document, RDF
triple, or cleanup run ever exists for a write that never became visible.
This is the request-wide delivery contract for CRUD, publish, import,
batch, delete, and restore (#392) — new call sites that enqueue work
depending on the current transaction's row MUST use ``after_commit``, not
``enqueue`` directly.

``enqueue(task, *args, **kwargs)`` — fire-and-forget dispatch for work that
is already safe to run (the referenced state is already durably committed,
e.g. because it is called from ``run_after_commit_hooks``, or because the
caller committed explicitly beforehand). If the Celery broker is
unreachable, log and carry on rather than turning a successful write into a
500 — matches the production-readiness posture where a broker outage
deliberately does not mark the API unhealthy (see /health, which skips
Redis). A broker outage at this point is logged and the delivery is
dropped: ES indexing/removal is self-healed by the periodic
``reconciliation_job_task`` (Layer 3 safety net, #214); RDF sync and
relation cleanup have no equivalent reconciliation today (see #392 issue
comment) and rely on the next edit of the affected record to catch up.

For the few endpoints that hand back a job id the client polls (media batch
import, record import), the broker is functionally required — those use
``enqueue_or_503`` instead, which surfaces a clear 503.
"""

import logging
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_HOOKS_KEY = "katalon_after_commit_hooks"


def enqueue(task: Any, *args: Any, **kwargs: Any) -> str | None:
    """Enqueue a task, swallowing broker errors. Returns the task id or None."""
    try:
        return cast(str, task.delay(*args, **kwargs).id)
    except Exception:
        logger.warning(
            "Celery enqueue failed for %s (broker down?) — continuing",
            getattr(task, "name", task),
            exc_info=True,
        )
        return None


def enqueue_or_503(task: Any, *args: Any, **kwargs: Any) -> str:
    """Enqueue a task whose id the caller needs; raise 503 if the broker is down."""
    try:
        return cast(str, task.delay(*args, **kwargs).id)
    except Exception as exc:
        logger.warning("Celery enqueue failed for %s", getattr(task, "name", task), exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Hintergrund-Verarbeitung derzeit nicht verfügbar (Broker nicht erreichbar).",
        ) from exc


def after_commit(db: AsyncSession, task: Any, *args: Any, **kwargs: Any) -> None:
    """Defer ``enqueue(task, *args, **kwargs)`` until ``db``'s transaction commits.

    Appends to a plain list on ``db.info`` — no broker interaction happens
    here, so this can never itself turn a write into a 500. Draining
    (``run_after_commit_hooks``) only happens where the caller has just
    observed ``await db.commit()`` succeed; a rollback simply never drains
    it, so nothing is ever dispatched for an uncommitted write.
    """
    hooks = db.info.setdefault(_HOOKS_KEY, [])
    hooks.append((task, args, kwargs))


async def run_after_commit_hooks(db: AsyncSession) -> None:
    """Dispatch every call ``after_commit`` deferred on ``db``, then clear them.

    MUST only be called immediately after a successful ``await db.commit()``.
    Safe to call unconditionally (e.g. every request teardown) — a no-op
    when nothing was deferred, and idempotent since the list is popped
    before dispatch.
    """
    hooks = db.info.pop(_HOOKS_KEY, None)
    if not hooks:
        return
    for task, args, kwargs in hooks:
        enqueue(task, *args, **kwargs)


def discard_after_commit_hooks(db: AsyncSession) -> None:
    """Drop any calls ``after_commit`` deferred on ``db`` without dispatching them.

    Call on rollback so a failed request never fires side effects for writes
    that never became durable.
    """
    db.info.pop(_HOOKS_KEY, None)
