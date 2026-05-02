import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select

from katalon.config import settings
from katalon.core.dependencies import CurrentUser, DBDep
from katalon.core.models import MediaFile, Object
from katalon.workers.media_tasks import generate_iiif_tiles

router = APIRouter(prefix="/objects/{object_id}/media", tags=["media"])

ALLOWED_MIME = {"image/jpeg", "image/png", "image/tiff", "image/webp"}


def _serialize(f: MediaFile) -> dict:
    return {
        "id": str(f.id),
        "filename": f.filename,
        "mime_type": f.mime_type,
        "status": f.status,
        "is_primary": f.is_primary,
        "media_type": f.media_type,
        "created_at": f.created_at.isoformat(),
    }


@router.get("", response_model=list[dict])
async def list_media(object_id: uuid.UUID, db: DBDep) -> list[dict]:
    result = await db.execute(select(MediaFile).where(MediaFile.object_id == object_id))
    return [_serialize(f) for f in result.scalars().all()]


@router.post("", status_code=201)
async def upload_media(object_id: uuid.UUID, file: UploadFile, db: DBDep, current_user: CurrentUser) -> dict:
    obj_result = await db.execute(select(Object).where(Object.id == object_id))
    if not obj_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden")

    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(status_code=415, detail=f"Nicht unterstützter Dateityp: {file.content_type}")

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    Path(settings.media_root).mkdir(parents=True, exist_ok=True)

    file_id = uuid.uuid4()
    suffix = Path(file.filename or "upload").suffix or ".bin"
    dest_path = Path(settings.media_root) / f"{file_id}{suffix}"

    size = 0
    async with aiofiles.open(dest_path, "wb") as out:
        while chunk := await file.read(65536):
            size += len(chunk)
            if size > max_bytes:
                dest_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="Datei zu groß")
            await out.write(chunk)

    existing = (await db.execute(select(MediaFile).where(MediaFile.object_id == object_id))).scalars().all()
    media = MediaFile(
        id=file_id,
        object_id=object_id,
        filename=file.filename or dest_path.name,
        mime_type=file.content_type,
        file_path=str(dest_path),
        status="pending",
        is_primary=len(existing) == 0,
    )
    db.add(media)
    await db.flush()

    generate_iiif_tiles.delay(str(file_id))

    return _serialize(media)


class MediaPatch(BaseModel):
    media_type: str | None = None
    is_primary: bool | None = None


@router.patch("/{media_id}", response_model=dict)
async def patch_media(
    object_id: uuid.UUID, media_id: uuid.UUID, data: MediaPatch, db: DBDep, current_user: CurrentUser
) -> dict:
    result = await db.execute(select(MediaFile).where(MediaFile.id == media_id, MediaFile.object_id == object_id))
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(status_code=404, detail="Medium nicht gefunden")

    if data.media_type is not None:
        media.media_type = data.media_type

    if data.is_primary is True:
        all_files = (await db.execute(select(MediaFile).where(MediaFile.object_id == object_id))).scalars().all()
        for f in all_files:
            f.is_primary = f.id == media_id
    elif data.is_primary is False:
        media.is_primary = False

    await db.flush()
    return _serialize(media)


@router.get("/{media_id}/file")
async def serve_media_file(object_id: uuid.UUID, media_id: uuid.UUID, db: DBDep) -> FileResponse:
    result = await db.execute(select(MediaFile).where(MediaFile.id == media_id, MediaFile.object_id == object_id))
    media = result.scalar_one_or_none()
    if not media or not Path(media.file_path).exists():
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    return FileResponse(media.file_path, media_type=media.mime_type, filename=media.filename)


@router.delete("/{media_id}", status_code=204)
async def delete_media(object_id: uuid.UUID, media_id: uuid.UUID, db: DBDep, current_user: CurrentUser) -> None:
    result = await db.execute(select(MediaFile).where(MediaFile.id == media_id, MediaFile.object_id == object_id))
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(status_code=404, detail="Medium nicht gefunden")
    Path(media.file_path).unlink(missing_ok=True)
    await db.delete(media)
