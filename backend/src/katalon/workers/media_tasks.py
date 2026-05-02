import asyncio
import uuid
from pathlib import Path

from sqlalchemy import select

from katalon.workers.celery_app import celery_app


async def _process(media_file_id: uuid.UUID) -> dict:
    from katalon.database import AsyncSessionLocal
    from katalon.core.models import MediaFile
    from katalon.integrations.cantaloupe import build_manifest, fetch_image_info

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(MediaFile).where(MediaFile.id == media_file_id))
        media = result.scalar_one_or_none()
        if not media:
            return {"status": "error", "detail": "not found"}

        filename = Path(media.file_path).name

        # Trigger Cantaloupe processing and get image dimensions for IIIF canvas
        width, height = await fetch_image_info(filename)

        manifest = build_manifest(media_file_id, filename, width=width, height=height)
        media.iiif_manifest = manifest
        media.status = "ready"
        await session.commit()
        return {"status": "ok", "manifest": manifest}


@celery_app.task(bind=True, max_retries=3)
def generate_iiif_tiles(self, media_file_id: str) -> dict:
    try:
        return asyncio.run(_process(uuid.UUID(media_file_id)))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 10)
