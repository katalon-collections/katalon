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
        "katalon.workers.cleanup_tasks",
        "katalon.workers.purge_tasks",
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
}
