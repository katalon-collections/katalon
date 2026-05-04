from celery import Celery

from katalon.config import settings

celery_app = Celery(
    "katalon",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["katalon.workers.media_tasks", "katalon.workers.index_tasks", "katalon.workers.import_tasks"],
)

celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.task_track_started = True
celery_app.conf.task_acks_late = True
