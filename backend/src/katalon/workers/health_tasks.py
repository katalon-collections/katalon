# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import logging
from datetime import UTC, datetime

from katalon.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# #396: dead-man's-switch liveness signal for Celery Beat + Worker together.
#
# Beat enqueues this task every 2 minutes (see celery_app.beat_schedule); a
# Worker has to actually pick it up and run it to refresh this key. If the
# key is missing, that's unambiguous evidence *something* in the
# scheduling/consumption chain stopped — Beat itself died, no Worker is
# consuming the queue, or Redis is unreachable. This deliberately does not
# try to distinguish those causes: from an operator's point of view all
# three are an outage that needs the same first response (check the
# containers), and building a check that tells them apart would need more
# moving parts (a separate Beat-side write, worker process introspection)
# than the failure mode is worth. `/health`'s `beat_heartbeat` check reads
# this key; see backend/src/katalon/main.py.
HEARTBEAT_KEY = "katalon:beat:heartbeat"
HEARTBEAT_TTL_SECONDS = 600  # 10 min: generous headroom over the 2 min schedule


@celery_app.task(name="katalon.heartbeat")
def heartbeat() -> None:
    """Refresh the Beat/Worker liveness key in Redis. See HEARTBEAT_KEY above."""
    import redis as redis_lib

    from katalon.config import settings

    client = redis_lib.from_url(settings.redis_url)
    client.set(HEARTBEAT_KEY, datetime.now(UTC).isoformat(), ex=HEARTBEAT_TTL_SECONDS)
