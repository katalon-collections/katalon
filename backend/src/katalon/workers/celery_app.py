# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from celery import Celery
from celery.schedules import crontab

from katalon.config import settings

celery_app = Celery(
    "katalon",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "katalon.workers.media_tasks",
        "katalon.workers.index_tasks",
        "katalon.workers.import_tasks",
        "katalon.workers.batch_tasks",
        "katalon.workers.purge_tasks",
        "katalon.workers.email_tasks",
        "katalon.workers.rdf_tasks",
        "katalon.workers.health_tasks",
    ],
)

celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.task_track_started = True
celery_app.conf.task_acks_late = True

# Layer 3 (#214): reconciliation safety net — daily count check, weekly ID-diff
celery_app.conf.beat_schedule = {
    "reconciliation-count-daily": {
        "task": "katalon.reconciliation_job",
        "schedule": crontab(hour=3, minute=0),
        "kwargs": {"mode": "count"},
    },
    "reconciliation-id-diff-weekly": {
        "task": "katalon.reconciliation_job",
        "schedule": crontab(hour=4, minute=0, day_of_week=0),
        "kwargs": {"mode": "id_diff"},
    },
    "purge-soft-deleted-daily": {
        "task": "katalon.purge_soft_deleted",
        "schedule": crontab(hour=5, minute=0),
    },
    # #390: retries physical storage deletion for MediaFile rows whose
    # deletion intent is already committed (deleted_at set) but whose
    # physical cleanup did not (yet) fully succeed — worker crash between
    # commit and physical delete, storage outage, or S3 partial-batch
    # failure. Frequent and idempotent on purpose: a failed delete should
    # not sit unretried for a whole day like the purge sweep above.
    "sweep-pending-media-deletes": {
        "task": "katalon.sweep_pending_media_deletes",
        "schedule": crontab(minute="*/15"),
    },
    # #396: dead-man's-switch liveness signal for Beat + Worker together — see
    # workers/health_tasks.py for the reasoning and the /health integration.
    "heartbeat": {
        "task": "katalon.heartbeat",
        "schedule": crontab(minute="*/2"),
    },
}
