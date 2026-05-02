import asyncio
import uuid
from pathlib import Path

from sqlalchemy import select

from katalon.workers.celery_app import celery_app


async def _process(media_file_id: uuid.UUID) -> dict:
    from katalon.database import AsyncSessionLocal
    from katalon.core.models import MediaFile
    from katalon.integrations.cantaloupe import CantaloupeError, build_manifest, fetch_image_info

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(MediaFile).where(MediaFile.id == media_file_id))
        media = result.scalar_one_or_none()
        if not media:
            return {"status": "error", "detail": "not found"}

        filename = Path(media.file_path).name

        try:
            # Trigger Cantaloupe processing and get image dimensions for IIIF canvas
            width, height = await fetch_image_info(filename)
        except CantaloupeError as exc:
            media.status = "error"
            await session.commit()
            return {"status": "error", "detail": str(exc)}

        manifest = build_manifest(media_file_id, filename, width=width, height=height)
        media.iiif_manifest = manifest
        media.status = "ready"
        await session.commit()
        return {"status": "ok", "manifest": manifest}


async def _set_error(media_file_id: uuid.UUID, detail: str) -> None:
    from katalon.database import AsyncSessionLocal
    from katalon.core.models import MediaFile

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(MediaFile).where(MediaFile.id == media_file_id))
        media = result.scalar_one_or_none()
        if media:
            media.status = "error"
            await session.commit()


@celery_app.task(bind=True, max_retries=3)
def generate_iiif_tiles(self, media_file_id: str) -> dict:
    try:
        return asyncio.run(_process(uuid.UUID(media_file_id)))
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            asyncio.run(_set_error(uuid.UUID(media_file_id), str(exc)))
            return {"status": "error", "detail": str(exc)}
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 10)
