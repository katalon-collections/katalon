"""Broker-tolerant Celery enqueue helpers.

Fire-and-forget background work (reindex, tile generation, relation cleanup)
must never break the HTTP request that triggered it: the primary DB write has
already succeeded by the time we enqueue. If the Celery broker is unreachable,
we log and carry on rather than turning a successful write into a 500. This
matches the production-readiness posture where a broker outage deliberately
does not mark the API unhealthy (see /health, which skips Redis).

For the few endpoints that hand back a job id the client polls (media batch
import, record import), the broker is functionally required — those use
``enqueue_or_503`` instead, which surfaces a clear 503.
"""

import logging
from typing import Any, cast

from fastapi import HTTPException

logger = logging.getLogger(__name__)


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
