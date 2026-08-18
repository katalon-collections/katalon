import io
import shutil
import uuid
import zipfile
from pathlib import Path
from urllib.parse import urlparse

import aiofiles
from celery.result import AsyncResult
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select

from katalon.config import settings
from katalon.core.dependencies import DBDep, OptionalCurrentUser, require_admin_or_editor
from katalon.core.media_validation import ALLOWED_MEDIA_MIME, media_category, resolve_upload_mime, verified_image_mime
from katalon.core.models import AdminConfig, MediaFile, Object
from katalon.core.visibility import ensure_publicly_visible
from katalon.integrations.cantaloupe import public_iiif_base
from katalon.services.audit_service import diff_fields, log_change
from katalon.workers.celery_app import celery_app
from katalon.workers.media_tasks import generate_iiif_tiles, import_media_batch_task

router = APIRouter(prefix="/objects/{object_id}/media", tags=["media"])
batch_router = APIRouter(prefix="/media", tags=["media"])

ALLOWED_MIME = ALLOWED_MEDIA_MIME


def _is_absolute_http_url(value: str) -> bool:
    if any(ord(char) < 32 for char in value):
        return False
    try:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and parsed.hostname is not None
    except ValueError:
        return False


def _serialize(f: MediaFile) -> dict:
    links = {
        "object": {"href": f"/v1/objects/{f.object_id}"},
        "file": {"href": f"/v1/objects/{f.object_id}/media/{f.id}/file"},
    }
    if f.status == "ready" and media_category(f.mime_type) == "image":
        identifier = Path(f.file_path).name
        links["thumbnail"] = {"href": f"{public_iiif_base()}/iiif/3/{identifier}/full/,300/0/default.jpg"}
    if f.license_uri and _is_absolute_http_url(f.license_uri):
        links["license"] = {"href": f.license_uri}
    return {
        "id": str(f.id),
        "filename": f.filename,
        "mime_type": f.mime_type,
        "category": media_category(f.mime_type),
        "status": f.status,
        "is_primary": f.is_primary,
        "media_type": f.media_type,
        "license_uri": f.license_uri,
        "rights_holder": f.rights_holder,
        "created_at": f.created_at.isoformat(),
        "_links": links,
    }


@router.get(
    "",
    response_model=list[dict],
    summary="List media files for an object",
    responses={404: {"description": "Object not found"}},
)
async def list_media(object_id: uuid.UUID, db: DBDep, current_user: OptionalCurrentUser) -> list[dict]:
    obj_result = await db.execute(select(Object).where(Object.id == object_id))
    obj = obj_result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden")
    ensure_publicly_visible(obj, current_user, "Objekt nicht gefunden")
    query = select(MediaFile).where(MediaFile.object_id == object_id)
    if current_user is None:
        query = query.where(MediaFile.status == "ready")
    result = await db.execute(query)
    return [_serialize(f) for f in result.scalars().all()]


@router.post(
    "",
    status_code=201,
    summary="Upload a media file for an object",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Object not found"},
        413: {"description": "File too large"},
        415: {"description": "Unsupported file type"},
    },
)
async def upload_media(object_id: uuid.UUID, file: UploadFile, db: DBDep, current_user=require_admin_or_editor()) -> dict:
    obj_result = await db.execute(select(Object).where(Object.id == object_id))
    if not obj_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden")

    resolved_mime = resolve_upload_mime(file.content_type, file.filename or "")
    if resolved_mime is None:
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

    category = media_category(resolved_mime)
    actual_mime = verified_image_mime(dest_path) if category == "image" else resolved_mime

    existing = (await db.execute(select(MediaFile).where(MediaFile.object_id == object_id))).scalars().all()
    config = await db.scalar(select(AdminConfig).where(AdminConfig.key == "default"))
    media = MediaFile(
        id=file_id,
        object_id=object_id,
        filename=file.filename or dest_path.name,
        mime_type=actual_mime,
        file_path=str(dest_path),
        status="pending" if category == "image" else "ready",
        is_primary=len(existing) == 0,
        license_uri=config.media_default_license_uri if config else None,
        rights_holder=config.media_default_rights_holder if config else None,
    )
    db.add(media)
    await log_change(
        db,
        record_type="object",
        record_id=object_id,
        user_id=current_user.id,
        action="media_add",
        changed_fields={"filename": media.filename, "mime_type": media.mime_type},
    )
    await db.commit()  # commit before Celery dispatch so the worker can find the row

    if category == "image":
        from katalon.workers.enqueue import enqueue
        enqueue(generate_iiif_tiles, str(file_id))

    return _serialize(media)


class MediaPatch(BaseModel):
    media_type: str | None = None
    is_primary: bool | None = None
    license_uri: str | None = None
    rights_holder: dict | None = None


@router.patch(
    "/{media_id}",
    response_model=dict,
    summary="Update media file metadata",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Media file not found"},
    },
)
async def patch_media(
    object_id: uuid.UUID, media_id: uuid.UUID, data: MediaPatch, db: DBDep, current_user=require_admin_or_editor()
) -> dict:
    result = await db.execute(select(MediaFile).where(MediaFile.id == media_id, MediaFile.object_id == object_id))
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(status_code=404, detail="Medium nicht gefunden")

    old_fields = {
        "media_type": media.media_type,
        "license_uri": media.license_uri,
        "rights_holder": media.rights_holder,
        "is_primary": media.is_primary,
    }

    if data.media_type is not None:
        media.media_type = data.media_type
    if "license_uri" in data.model_fields_set:
        media.license_uri = data.license_uri
    if "rights_holder" in data.model_fields_set:
        media.rights_holder = data.rights_holder

    if data.is_primary is True:
        all_files = (await db.execute(select(MediaFile).where(MediaFile.object_id == object_id))).scalars().all()
        for f in all_files:
            f.is_primary = f.id == media_id
    elif data.is_primary is False:
        media.is_primary = False

    diff = diff_fields(old_fields, {
        "media_type": media.media_type,
        "license_uri": media.license_uri,
        "rights_holder": media.rights_holder,
        "is_primary": media.is_primary,
    })
    if diff:
        diff["filename"] = media.filename
        await log_change(
            db, record_type="object", record_id=object_id, user_id=current_user.id,
            action="media_update", changed_fields=diff,
        )

    await db.flush()
    return _serialize(media)


@router.get(
    "/{media_id}/file",
    summary="Serve the raw media file",
    responses={404: {"description": "Object, media file, or file on disk not found"}},
)
async def serve_media_file(
    object_id: uuid.UUID, media_id: uuid.UUID, db: DBDep, current_user: OptionalCurrentUser
) -> FileResponse:
    obj_result = await db.execute(select(Object).where(Object.id == object_id))
    obj = obj_result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Objekt nicht gefunden")
    ensure_publicly_visible(obj, current_user, "Objekt nicht gefunden")
    query = select(MediaFile).where(MediaFile.id == media_id, MediaFile.object_id == object_id)
    if current_user is None:
        query = query.where(MediaFile.status == "ready")
    result = await db.execute(query)
    media = result.scalar_one_or_none()
    if not media or not Path(media.file_path).exists():
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    return FileResponse(media.file_path, media_type=media.mime_type, filename=media.filename)


@router.delete(
    "/{media_id}",
    status_code=204,
    summary="Delete a media file",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Media file not found"},
    },
)
async def delete_media(object_id: uuid.UUID, media_id: uuid.UUID, db: DBDep, current_user=require_admin_or_editor()) -> None:
    result = await db.execute(select(MediaFile).where(MediaFile.id == media_id, MediaFile.object_id == object_id))
    media = result.scalar_one_or_none()
    if not media:
        raise HTTPException(status_code=404, detail="Medium nicht gefunden")
    Path(media.file_path).unlink(missing_ok=True)
    await log_change(
        db,
        record_type="object",
        record_id=object_id,
        user_id=current_user.id,
        action="media_delete",
        changed_fields={"filename": media.filename},
    )
    await db.delete(media)


def _safe_join(root: Path, relative: str) -> Path:
    rel = Path(relative)
    target = (root / rel).resolve()
    if not target.is_relative_to(root.resolve()):
        raise HTTPException(status_code=400, detail="Ungültiger Dateipfad im Archiv")
    return target


@batch_router.post(
    "/batch-import",
    dependencies=[require_admin_or_editor()],
    summary="Start a batch media import job from a ZIP archive or file list",
    responses={
        403: {"description": "Insufficient permissions"},
        422: {"description": "Missing or invalid archive, files, or mapping file"},
        503: {"description": "Background task queue unavailable (broker down)"},
    },
)
async def start_batch_import(
    archive: UploadFile | None = File(None),
    mapping: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
) -> dict:
    if archive is None and not files:
        raise HTTPException(status_code=422, detail="Bitte ZIP-Datei oder Bildordner hochladen")

    if archive is not None and archive.filename and not archive.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=422, detail="Archiv muss eine ZIP-Datei sein")

    staging_root = Path(settings.media_root) / "_batch_imports"
    staging_root.mkdir(parents=True, exist_ok=True)
    job_id = uuid.uuid4()
    job_dir = staging_root / str(job_id)
    images_dir = job_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    if archive is not None:
        archive_bytes = await archive.read()
        try:
            with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    output_path = _safe_join(images_dir, info.filename)
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as src, output_path.open("wb") as dst:
                        shutil.copyfileobj(src, dst)
        except zipfile.BadZipFile as exc:
            shutil.rmtree(job_dir, ignore_errors=True)
            raise HTTPException(status_code=422, detail=f"Ungültiges ZIP-Archiv: {exc}") from exc

    for upload in files or []:
        if not upload.filename:
            shutil.rmtree(job_dir, ignore_errors=True)
            raise HTTPException(status_code=422, detail="Upload enthält Datei ohne Namen")
        output_path = _safe_join(images_dir, upload.filename)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(output_path, "wb") as out:
            while chunk := await upload.read(65536):
                await out.write(chunk)

    if mapping is not None:
        mapping_name = (mapping.filename or "").lower()
        if not (mapping_name.endswith(".csv") or mapping_name.endswith(".tsv")):
            shutil.rmtree(job_dir, ignore_errors=True)
            raise HTTPException(status_code=422, detail="Mapping-Datei muss CSV/TSV sein")
        mapping_path = job_dir / "mapping.csv"
        async with aiofiles.open(mapping_path, "wb") as out:
            while chunk := await mapping.read(65536):
                await out.write(chunk)

    from katalon.workers.enqueue import enqueue_or_503
    task_id = enqueue_or_503(import_media_batch_task, str(job_id), str(job_dir))
    return {"status": "queued", "task_id": task_id, "batch_id": str(job_id)}


@batch_router.get(
    "/batch-import/task/{task_id}",
    dependencies=[require_admin_or_editor()],
    summary="Get the status of a batch media import task",
    responses={403: {"description": "Insufficient permissions"}},
)
async def batch_import_status(task_id: str) -> dict:
    result = AsyncResult(task_id, app=celery_app)
    state = result.state
    meta = result.info if isinstance(result.info, dict) else None
    if state == "SUCCESS":
        return {"state": state, "result": result.result}
    if state == "FAILURE":
        return {"state": state, "error": str(result.result), "meta": meta}
    return {"state": state, "meta": meta}
