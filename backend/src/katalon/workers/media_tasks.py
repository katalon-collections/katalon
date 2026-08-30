import asyncio
import logging
import shutil
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from katalon.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _make_pyramid_tiff(source_path: Path) -> Path | None:
    """Convert source image to a tiled, pyramidal TIFF for fast IIIF random-access reads.

    Returns None on failure so callers can fall back to serving the original.
    """
    dest_path = source_path.with_name(f"{source_path.stem}_pyramid.tif")
    try:
        import pyvips

        image = pyvips.Image.new_from_file(str(source_path), access="sequential")
        image.tiffsave(
            str(dest_path),
            tile=True,
            pyramid=True,
            compression="jpeg",
            Q=85,
        )
        return dest_path
    except Exception:
        logger.warning("Pyramid-TIFF-Konvertierung fehlgeschlagen für %s", source_path, exc_info=True)
        dest_path.unlink(missing_ok=True)
        return None


def _worker_session() -> async_sessionmaker[AsyncSession]:
    from katalon.config import settings
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def _process(media_file_id: uuid.UUID) -> dict[str, Any]:
    from katalon.core.models import MediaFile
    from katalon.integrations.cantaloupe import CantaloupeError, build_manifest, fetch_image_info

    async with _worker_session()() as session:
        result = await session.execute(select(MediaFile).where(MediaFile.id == media_file_id))
        media = result.scalar_one_or_none()
        if not media:
            raise ValueError(f"MediaFile {media_file_id} not found")

        source_path = Path(media.file_path)
        pyramid_path = await asyncio.to_thread(_make_pyramid_tiff, source_path)
        if pyramid_path is not None:
            media.iiif_source_path = str(pyramid_path)
        filename = pyramid_path.name if pyramid_path is not None else source_path.name

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
    from katalon.core.models import MediaFile

    async with _worker_session()() as session:
        result = await session.execute(select(MediaFile).where(MediaFile.id == media_file_id))
        media = result.scalar_one_or_none()
        if media:
            media.status = "error"
            await session.commit()


@celery_app.task(bind=True, max_retries=3)
def generate_iiif_tiles(self: Any, media_file_id: str) -> dict[str, Any]:
    try:
        return asyncio.run(_process(uuid.UUID(media_file_id)))
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            asyncio.run(_set_error(uuid.UUID(media_file_id), str(exc)))
            return {"status": "error", "detail": str(exc)}
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 10)


async def _import_media_batch(job_id: uuid.UUID, job_dir: Path, task: Any) -> dict[str, Any]:
    from katalon.config import settings
    from katalon.core.media_validation import ALLOWED_IMAGE_MIME, verified_image_mime
    from katalon.core.models import (
        AdminConfig,
        MediaFile,
        MediaImportReference,
        Object,
        Vocabulary,
        VocabularyTerm,
    )
    from katalon.services.media_batch_import_service import (
        folder_or_filename_object_id,
        normalize_filename,
        parse_mapping_csv,
    )

    images_dir = job_dir / "images"
    mapping_path = job_dir / "mapping.csv"
    files = [p for p in images_dir.rglob("*") if p.is_file()]

    by_basename: dict[str, list[Path]] = {}
    for f in files:
        by_basename.setdefault(normalize_filename(f.name), []).append(f)

    report: dict[str, list[dict[str, str | int | None]]] = {
        "missing_files": [],
        "duplicate_files": [],
        "unmatched_files": [],
        "errors": [],
    }

    planned: list[tuple[Path, str, str | None]] = []
    automatic_files: list[Path] = []
    if mapping_path.exists():
        rows, mapping_errors = parse_mapping_csv(mapping_path.read_bytes())
        report["errors"].extend(mapping_errors)
        explicitly_mapped: set[Path] = set()
        explicit_targets: dict[Path, set[tuple[str, str | None]]] = {}
        for row in rows if not mapping_errors else []:
            matches = by_basename.get(normalize_filename(row.filename), [])
            if not matches:
                report["missing_files"].append({"row": row.row, "filename": row.filename})
                continue
            if len(matches) > 1:
                report["duplicate_files"].append({"row": row.row, "filename": row.filename})
                continue
            explicitly_mapped.add(matches[0])
            explicit_targets.setdefault(matches[0], set()).add(
                (row.object_id, row.media_type)
            )
        for file_path, targets in explicit_targets.items():
            if len(targets) > 1:
                report["errors"].append({
                    "row": None,
                    "message": (
                        f"Datei {file_path.name} hat mehrere unterschiedliche CSV-Ziele"
                    ),
                })
                continue
            explicit_object_id, explicit_media_type = next(iter(targets))
            planned.append((file_path, explicit_object_id, explicit_media_type))
        if not mapping_errors:
            automatic_files = [
                file_path for file_path in files if file_path not in explicitly_mapped
            ]
    else:
        automatic_files = files

    for name, dup in by_basename.items():
        if len(dup) > 1:
            report["duplicate_files"].append({"row": None, "filename": name, "count": len(dup)})

    created = 0
    skipped = 0
    failed = 0
    processed = 0

    async with _worker_session()() as session:
        config = await session.scalar(select(AdminConfig).where(AdminConfig.key == "default"))
        vocab_result = await session.execute(select(Vocabulary).where(Vocabulary.name == "media_types"))
        vocab = vocab_result.scalar_one_or_none()
        media_terms: set[str] = set()
        if vocab is not None:
            terms_result = await session.execute(
                select(VocabularyTerm.term).where(VocabularyTerm.vocabulary_id == vocab.id)
            )
            media_terms = {t for t in terms_result.scalars().all()}
        media_vocab_ready = vocab is not None and bool(media_terms)

        references_by_name: dict[str, list[MediaImportReference]] = {}
        if automatic_files:
            normalized_names = list(by_basename)
            pending_references = (await session.execute(
                select(MediaImportReference).where(
                    MediaImportReference.normalized_filename.in_(normalized_names)
                )
            )).scalars().all()
            for pending_reference in pending_references:
                references_by_name.setdefault(
                    pending_reference.normalized_filename, []
                ).append(pending_reference)

        for file_path in automatic_files:
            normalized = normalize_filename(file_path.name)
            if len(by_basename[normalized]) > 1:
                continue
            references = references_by_name.get(normalized, [])
            object_ids = {reference.object_id for reference in references}
            rel = str(file_path.relative_to(images_dir))
            if len(object_ids) > 1:
                report["errors"].append({
                    "row": None,
                    "message": f"Datei {rel} ist mehreren Objekten zugeordnet",
                })
                continue
            if references:
                reference = references[0]
                planned.append((file_path, str(reference.object_id), None))
                continue
            object_id = folder_or_filename_object_id(rel)
            if not object_id:
                report["unmatched_files"].append({"filename": rel})
                continue
            planned.append((file_path, object_id, None))

        total = len(planned)

        media_root = Path(settings.media_root)
        media_root.mkdir(parents=True, exist_ok=True)

        for file_path, object_id_raw, media_type in planned:
            processed += 1
            task.update_state(
                state="STARTED",
                meta={
                    "total": total,
                    "processed": processed,
                    "created": created,
                    "skipped": skipped,
                    "failed": failed,
                },
            )
            rel_name = str(file_path.relative_to(images_dir))
            try:
                object_uuid = uuid.UUID(object_id_raw)
            except ValueError:
                failed += 1
                report["errors"].append({"row": None, "message": f"Ungültige Objekt-ID für Datei {rel_name}"})
                continue

            object_exists = (
                await session.execute(select(Object.id).where(Object.id == object_uuid))
            ).scalar_one_or_none()
            if object_exists is None:
                failed += 1
                report["errors"].append({"row": None, "message": f"Objekt nicht gefunden für Datei {rel_name}"})
                continue

            if media_type and not media_vocab_ready:
                failed += 1
                report["errors"].append({
                    "row": None,
                    "message": f"media_types-Vokabular nicht verfügbar für Datei {rel_name}",
                })
                continue
            if media_type and media_type not in media_terms:
                failed += 1
                report["errors"].append({
                    "row": None,
                    "message": f"Ungültiger media_type '{media_type}' für Datei {rel_name}",
                })
                continue

            existing_filenames = (
                await session.execute(
                    select(MediaFile.filename).where(MediaFile.object_id == object_uuid)
                )
            ).scalars().all()
            if any(normalize_filename(filename) == normalize_filename(file_path.name) for filename in existing_filenames):
                skipped += 1
                continue

            file_id = uuid.uuid4()
            suffix = file_path.suffix or ".bin"
            dest_path = media_root / f"{file_id}{suffix}"
            shutil.copy2(file_path, dest_path)
            try:
                mime = verified_image_mime(dest_path)
            except Exception:
                dest_path.unlink(missing_ok=True)
                failed += 1
                report["errors"].append({
                    "row": None,
                    "message": f"Nicht unterstützter Dateityp für Datei {rel_name}",
                })
                continue
            if mime not in ALLOWED_IMAGE_MIME:
                dest_path.unlink(missing_ok=True)
                failed += 1
                report["errors"].append({
                    "row": None,
                    "message": f"Nicht unterstützter Dateityp für Datei {rel_name}",
                })
                continue

            existing = (
                await session.execute(select(MediaFile.id).where(MediaFile.object_id == object_uuid))
            ).scalars().first()
            media = MediaFile(
                id=file_id,
                object_id=object_uuid,
                filename=file_path.name,
                mime_type=mime,
                file_path=str(dest_path),
                status="pending",
                is_primary=existing is None,
                media_type=media_type,
                license_uri=config.media_default_license_uri if config else None,
                rights_holder=config.media_default_rights_holder if config else None,
            )
            session.add(media)
            await session.flush()

            generate_iiif_tiles.delay(str(file_id))
            created += 1

        await session.commit()

    return {
        "batch_id": str(job_id),
        "total_files": len(files),
        "planned": total,
        "created": created,
        "skipped": skipped,
        "failed": failed,
        "report": report,
    }


@celery_app.task(name="katalon.import_media_batch", bind=True)
def import_media_batch_task(self: Any, job_id: str, job_dir: str) -> dict[str, Any]:
    try:
        result = asyncio.run(_import_media_batch(uuid.UUID(job_id), Path(job_dir), self))
        try:
            shutil.rmtree(job_dir, ignore_errors=False)
        except OSError:
            pass
        return result
    except Exception as exc:
        try:
            shutil.rmtree(job_dir, ignore_errors=False)
        except OSError:
            pass
        raise exc
