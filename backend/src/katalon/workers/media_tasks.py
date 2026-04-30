import uuid

from katalon.workers.celery_app import celery_app


@celery_app.task(bind=True, max_retries=3)
def generate_iiif_tiles(self, media_file_id: str) -> dict:
    """Process uploaded image: generate tiles via Cantaloupe, build IIIF manifest."""
    from katalon.integrations.cantaloupe import build_manifest
    try:
        manifest = build_manifest(uuid.UUID(media_file_id))
        return {"status": "ok", "manifest": manifest}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 10)
