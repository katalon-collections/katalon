# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Redis-backed coordination for bulk reindex jobs.

A bulk reindex always rebuilds from current DB state, so any number of
requests that arrive before a job *starts* are served by that one job, and any
number that arrive while it *runs* are served by exactly one follow-up job.
Rebuilds run one at a time (single run lock): parallel rebuilds only compete
for the same CPU and DB, and a full rebuild into a fresh index must not race
an in-place rebuild of the old one. Keys (``<type>`` is a record type, or
``__all__`` for the full rebuild):

``katalon:reindex:run``             the run lock (short lease, renewed by a
                                    watchdog thread while the job runs)
``katalon:reindex:<type>:queued``   a coalescing job is waiting in the broker
``katalon:reindex:<type>:dirty``    a change is pending; cleared only after a
                                    successful run that started after it
``katalon:reindex:<type>:progress`` hash read by GET /v1/admin/index-status

Every Redis failure fails open (enqueue anyway): a duplicate rebuild costs
time, a silently skipped one leaves the portal stale.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

KEY_PREFIX = "katalon:reindex"
# Lease of the run lock. A crashed worker blocks the type for at most this long;
# the watchdog renews it every LOCK_RENEW_SECONDS while the job is alive.
LOCK_TTL_SECONDS = 120
LOCK_RENEW_SECONDS = 30
# Upper bound for a "queued" marker whose broker message got lost. A second job
# enqueued after expiry is harmless: it finds no dirty flag and skips.
QUEUED_TTL_SECONDS = 3600
DIRTY_TTL_SECONDS = 24 * 3600
PROGRESS_TTL_SECONDS = 24 * 3600


FULL = "__all__"
RUN_LOCK_KEY = f"{KEY_PREFIX}:run"


def run_lock(client: Any) -> Any:
    return client.lock(RUN_LOCK_KEY, timeout=LOCK_TTL_SECONDS, thread_local=False)


def queued_key(target_type: str) -> str:
    return f"{KEY_PREFIX}:{target_type}:queued"


def dirty_key(target_type: str) -> str:
    return f"{KEY_PREFIX}:{target_type}:dirty"


def progress_key(target_type: str) -> str:
    return f"{KEY_PREFIX}:{target_type}:progress"


def mark_dirty(client: Any, target_type: str) -> None:
    """Record a pending change. Each mark gets a fresh token, so a running job
    can tell whether new changes arrived while it ran."""
    client.set(dirty_key(target_type), f"{now_iso()}|{uuid.uuid4().hex}", ex=DIRTY_TTL_SECONDS)


_CLEAR_IF_UNCHANGED = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""


def clear_dirty_if_unchanged(client: Any, target_type: str, token: str) -> bool:
    return bool(client.eval(_CLEAR_IF_UNCHANGED, 1, dirty_key(target_type), token))


def resubmit_pending(target_types: list[str]) -> list[str]:
    """Request a rebuild for every type (and the full rebuild) with a pending
    change that is not waiting, unless a rebuild is running — that one
    resubmits when it ends. Returns the names that were (re)requested."""
    client = redis_client()
    try:
        if client.exists(RUN_LOCK_KEY):
            return []
        pending = [
            name
            for name in [FULL, *target_types]
            if client.exists(dirty_key(name)) and not client.exists(queued_key(name))
        ]
    finally:
        client.close()
    for name in pending:
        logger.info("resubmitting pending reindex for '%s'", name)
        if name == FULL:
            request_full_rebuild()
        else:
            request_bulk_reindex(name)
    return pending


def redis_client() -> Any:
    import redis as redis_lib

    from katalon.config import settings

    return redis_lib.from_url(settings.redis_url, decode_responses=True)  # type: ignore[no-untyped-call]


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def request_bulk_reindex(target_type: str, *, strict: bool = False) -> bool:
    """Ask for a rebuild of ``target_type``; enqueue at most one waiting job.

    Returns True if a job was enqueued, False if an already waiting (or the
    running job's follow-up) covers this request. With ``strict`` a broker
    outage raises 503 (for endpoints that report "queued" to an admin).
    """
    from katalon.workers.index_tasks import bulk_reindex_type_task

    return _request(target_type, bulk_reindex_type_task, (target_type,), strict)


def request_full_rebuild(*, strict: bool = False) -> bool:
    """Ask for a full rebuild into a fresh index (alias swap); coalesces like
    ``request_bulk_reindex``."""
    from katalon.workers.index_tasks import reindex_all_task

    return _request(FULL, reindex_all_task, (), strict)


def _request(name: str, task: Any, args: tuple[Any, ...], strict: bool) -> bool:
    from katalon.workers.enqueue import enqueue, enqueue_or_503

    claimed = True
    client = None
    try:
        client = redis_client()
        mark_dirty(client, name)
        claimed = bool(client.set(queued_key(name), now_iso(), nx=True, ex=QUEUED_TTL_SECONDS))
    except Exception:
        logger.warning(
            "reindex coordination unavailable for '%s' — enqueueing anyway", name, exc_info=True
        )
        client = None
    if not claimed:
        return False

    try:
        if strict:
            enqueue_or_503(task, *args, coalesce=True)
            return True
        if enqueue(task, *args, coalesce=True) is not None:
            return True
        _release_queued_claim(client, name)
        return False
    except Exception:
        _release_queued_claim(client, name)
        raise
    finally:
        if client is not None:
            client.close()


def _release_queued_claim(client: Any, target_type: str) -> None:
    """Drop the queued marker when no message actually reached the broker,
    otherwise later requests would see a phantom waiting job."""
    if client is None:
        return
    try:
        client.delete(queued_key(target_type))
    except Exception:
        logger.warning("could not clear queued marker for '%s'", target_type, exc_info=True)


class LeaseWatchdog:
    """Keep a redis lock's lease alive while the owning job runs."""

    def __init__(self, lock: Any, interval: float = LOCK_RENEW_SECONDS) -> None:
        self._lock = lock
        self._interval = interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="reindex-lease", daemon=True)
        self.lost = False

    def __enter__(self) -> LeaseWatchdog:
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._stop.set()
        self._thread.join(timeout=self._interval + 5)

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                self._lock.reacquire()
            except Exception:
                self.lost = True
                logger.error("reindex lease renewal failed for %s", self._lock.name, exc_info=True)
                return


# Locks held by jobs in this worker process, released on worker shutdown so a
# deliberate restart never leaves a type blocked for the remaining lease.
_held_locks: set[Any] = set()
_held_locks_guard = threading.Lock()


def register_held_lock(lock: Any) -> None:
    with _held_locks_guard:
        _held_locks.add(lock)


def unregister_held_lock(lock: Any) -> None:
    with _held_locks_guard:
        _held_locks.discard(lock)


def release_all_held_locks() -> None:
    with _held_locks_guard:
        locks = list(_held_locks)
        _held_locks.clear()
    for lock in locks:
        try:
            lock.release()
        except Exception:
            logger.warning("could not release reindex lock %s on shutdown", lock.name)


class ProgressReporter:
    """Write throttled progress for one run into the type's progress hash."""

    def __init__(self, client: Any, target_type: str, task_id: str | None) -> None:
        self._client = client
        self._key = progress_key(target_type)
        self._last_write = 0.0
        self._write(
            {
                "state": "running",
                "task_id": task_id or "",
                "started_at": now_iso(),
                "finished_at": "",
                "total": 0,
                "built": 0,
                "indexed": 0,
                "error": "",
            },
            replace=True,
        )

    def _write(self, fields: dict[str, Any], *, replace: bool = False) -> None:
        try:
            pipe = self._client.pipeline()
            if replace:
                pipe.delete(self._key)
            pipe.hset(self._key, mapping={k: str(v) for k, v in fields.items()})
            pipe.expire(self._key, PROGRESS_TTL_SECONDS)
            pipe.execute()
        except Exception:
            logger.warning("could not write reindex progress %s", self._key, exc_info=True)

    def update(self, *, force: bool = False, **fields: Any) -> None:
        now = time.monotonic()
        if not force and now - self._last_write < 2:
            return
        self._last_write = now
        self._write(fields)

    def finish(self, state: str, **fields: Any) -> None:
        self._write({"state": state, "finished_at": now_iso(), **fields})


def read_status(target_types: list[str]) -> dict[str, dict[str, Any]]:
    """Current coordination state per type (and ``__all__``) for the admin
    status endpoint."""
    client = redis_client()
    try:
        locked = bool(client.exists(RUN_LOCK_KEY))
        out: dict[str, dict[str, Any]] = {}
        for name in [*target_types, FULL]:
            pipe = client.pipeline()
            pipe.hgetall(progress_key(name))
            pipe.exists(queued_key(name))
            pipe.exists(dirty_key(name))
            progress, queued, dirty = pipe.execute()
            out[name] = {
                "progress": progress or {},
                "queued": bool(queued),
                "dirty": bool(dirty),
                "locked": locked,
            }
        return out
    finally:
        client.close()
