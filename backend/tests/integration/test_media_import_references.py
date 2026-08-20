import asyncio
import uuid
from unittest.mock import MagicMock

import pytest
from PIL import Image
from sqlalchemy import select

from katalon.core.models import MediaImportReference, Object


@pytest.mark.asyncio
async def test_unknown_media_selector_blocks_dry_run_and_import(
    async_client, auth_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    from katalon.api.v1 import importer

    monkeypatch.setattr(
        importer,
        "_load_rows",
        lambda upload_id: [{"resourceID": "image.jpg"}],
    )
    body = {
        "upload_id": "test-upload",
        "record_type": "object",
        "mapping": {},
        "media_selector": "missing",
    }

    dry_response = await async_client.post(
        "/v1/importer/dry-run", headers=auth_headers, json=body
    )
    import_response = await async_client.post(
        "/v1/importer/import", headers=auth_headers, json=body
    )

    assert dry_response.status_code == 200
    assert "wurde nicht gefunden" in str(dry_response.json()["errors"])
    assert import_response.status_code == 422
    assert "wurde nicht gefunden" in import_response.json()["detail"]


@pytest.mark.asyncio
async def test_existing_skip_stores_media_references_without_changing_metadata(
    app, monkeypatch: pytest.MonkeyPatch
) -> None:
    from katalon.database import AsyncSessionLocal
    from katalon.workers.import_tasks import import_records_task

    idno = f"MEDIA-SKIP-{uuid.uuid4().hex}"
    async with AsyncSessionLocal() as session:
        obj = Object(idno=idno, metadata_={"title": "bestehend"})
        session.add(obj)
        await session.commit()
        object_id = obj.id

    class FakeRedis:
        def get(self, key: str) -> None:
            return None

    monkeypatch.setattr("redis.from_url", lambda *args, **kwargs: FakeRedis())
    monkeypatch.setattr(import_records_task, "update_state", lambda **kwargs: None)

    task_args = (
        "object",
        [{"recordID": idno, "resourceID": ["Vorne.JPG", "Hinten.jpg"]}],
        {"recordID": "__idno__"},
    )
    result = await asyncio.to_thread(
        import_records_task.run,
        *task_args,
        upsert_strategy="skip",
        media_selector="resourceID",
    )
    repeated_result = await asyncio.to_thread(
        import_records_task.run,
        *task_args,
        upsert_strategy="skip",
        media_selector="resourceID",
    )

    assert result["skipped"] == 1
    assert result["media_references_created"] == 2
    assert repeated_result["media_references_created"] == 0
    async with AsyncSessionLocal() as session:
        obj = await session.get(Object, object_id)
        assert obj is not None
        assert obj.metadata_ == {"title": "bestehend"}
        references = (await session.execute(
            select(MediaImportReference).where(MediaImportReference.object_id == object_id)
        )).scalars().all()
        assert {reference.normalized_filename for reference in references} == {
            "vorne.jpg",
            "hinten.jpg",
        }


@pytest.mark.asyncio
async def test_media_batch_consumes_only_successful_reference(
    app, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from katalon.config import settings
    from katalon.database import AsyncSessionLocal
    from katalon.workers.media_tasks import _import_media_batch, generate_iiif_tiles

    good_object = Object(idno=f"MEDIA-GOOD-{uuid.uuid4().hex}", metadata_={})
    bad_object = Object(idno=f"MEDIA-BAD-{uuid.uuid4().hex}", metadata_={})
    async with AsyncSessionLocal() as session:
        session.add_all([good_object, bad_object])
        await session.flush()
        good_reference = MediaImportReference(
            object_id=good_object.id,
            filename="good.png",
            normalized_filename="good.png",
        )
        bad_reference = MediaImportReference(
            object_id=bad_object.id,
            filename="bad.png",
            normalized_filename="bad.png",
        )
        session.add_all([good_reference, bad_reference])
        await session.commit()
        good_reference_id = good_reference.id
        bad_reference_id = bad_reference.id

    job_dir = tmp_path / "job"
    images_dir = job_dir / "images"
    images_dir.mkdir(parents=True)
    Image.new("RGB", (1, 1)).save(images_dir / "good.png")
    (images_dir / "bad.png").write_bytes(b"not an image")
    monkeypatch.setattr(settings, "media_root", str(tmp_path / "media"))
    monkeypatch.setattr(generate_iiif_tiles, "delay", lambda *args, **kwargs: None)

    result = await _import_media_batch(uuid.uuid4(), job_dir, MagicMock())

    assert result["created"] == 1
    assert result["failed"] == 1
    repeated_result = await _import_media_batch(uuid.uuid4(), job_dir, MagicMock())
    assert repeated_result["created"] == 0
    assert repeated_result["skipped"] == 1
    async with AsyncSessionLocal() as session:
        assert await session.get(MediaImportReference, good_reference_id) is not None
        assert await session.get(MediaImportReference, bad_reference_id) is not None


@pytest.mark.asyncio
async def test_manual_mapping_keeps_same_filename_reference_for_other_object(
    app, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from katalon.config import settings
    from katalon.database import AsyncSessionLocal
    from katalon.workers.media_tasks import _import_media_batch, generate_iiif_tiles

    mapped_object = Object(idno=f"MEDIA-MAPPED-{uuid.uuid4().hex}", metadata_={})
    other_object = Object(idno=f"MEDIA-OTHER-{uuid.uuid4().hex}", metadata_={})
    async with AsyncSessionLocal() as session:
        session.add_all([mapped_object, other_object])
        await session.flush()
        mapped_reference = MediaImportReference(
            object_id=mapped_object.id,
            filename="shared.png",
            normalized_filename="shared.png",
        )
        other_reference = MediaImportReference(
            object_id=other_object.id,
            filename="shared.png",
            normalized_filename="shared.png",
        )
        session.add_all([mapped_reference, other_reference])
        await session.commit()
        mapped_object_id = mapped_object.id
        mapped_reference_id = mapped_reference.id
        other_reference_id = other_reference.id

    job_dir = tmp_path / "manual-job"
    images_dir = job_dir / "images"
    images_dir.mkdir(parents=True)
    Image.new("RGB", (1, 1)).save(images_dir / "shared.png")
    (job_dir / "mapping.csv").write_text(
        f"filename,object_id\nshared.png,{mapped_object_id}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "media_root", str(tmp_path / "manual-media"))
    monkeypatch.setattr(generate_iiif_tiles, "delay", lambda *args, **kwargs: None)

    result = await _import_media_batch(uuid.uuid4(), job_dir, MagicMock())

    assert result["created"] == 1
    async with AsyncSessionLocal() as session:
        assert await session.get(MediaImportReference, mapped_reference_id) is not None
        assert await session.get(MediaImportReference, other_reference_id) is not None


@pytest.mark.asyncio
async def test_manual_mapping_deduplicates_identical_rows_and_blocks_distinct_targets(
    app, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from katalon.config import settings
    from katalon.database import AsyncSessionLocal
    from katalon.workers.media_tasks import _import_media_batch, generate_iiif_tiles

    first_object = Object(idno=f"MEDIA-FIRST-{uuid.uuid4().hex}", metadata_={})
    second_object = Object(idno=f"MEDIA-SECOND-{uuid.uuid4().hex}", metadata_={})
    async with AsyncSessionLocal() as session:
        session.add_all([first_object, second_object])
        await session.flush()
        conflict_reference = MediaImportReference(
            object_id=first_object.id,
            filename="conflict.png",
            normalized_filename="conflict.png",
        )
        session.add(conflict_reference)
        await session.commit()
        first_object_id = first_object.id
        second_object_id = second_object.id
        conflict_reference_id = conflict_reference.id

    monkeypatch.setattr(settings, "media_root", str(tmp_path / "dedupe-media"))
    monkeypatch.setattr(generate_iiif_tiles, "delay", lambda *args, **kwargs: None)

    duplicate_job = tmp_path / "duplicate-job"
    duplicate_images = duplicate_job / "images"
    duplicate_images.mkdir(parents=True)
    Image.new("RGB", (1, 1)).save(duplicate_images / "same.png")
    (duplicate_job / "mapping.csv").write_text(
        "filename,object_id\n"
        f"same.png,{first_object_id}\n"
        f"same.png,{first_object_id}\n",
        encoding="utf-8",
    )
    duplicate_result = await _import_media_batch(uuid.uuid4(), duplicate_job, MagicMock())
    assert duplicate_result["created"] == 1

    conflict_job = tmp_path / "conflict-job"
    conflict_images = conflict_job / "images"
    conflict_images.mkdir(parents=True)
    Image.new("RGB", (1, 1)).save(conflict_images / "conflict.png")
    (conflict_job / "mapping.csv").write_text(
        "filename,object_id\n"
        f"conflict.png,{first_object_id}\n"
        f"conflict.png,{second_object_id}\n",
        encoding="utf-8",
    )
    conflict_result = await _import_media_batch(uuid.uuid4(), conflict_job, MagicMock())

    assert conflict_result["created"] == 0
    assert "mehrere unterschiedliche CSV-Ziele" in str(conflict_result["report"]["errors"])
    async with AsyncSessionLocal() as session:
        assert await session.get(MediaImportReference, conflict_reference_id) is not None


@pytest.mark.asyncio
async def test_malformed_mapping_does_not_fall_back_to_pending_reference(
    app, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from katalon.config import settings
    from katalon.database import AsyncSessionLocal
    from katalon.workers.media_tasks import _import_media_batch, generate_iiif_tiles

    obj = Object(idno=f"MEDIA-MALFORMED-{uuid.uuid4().hex}", metadata_={})
    async with AsyncSessionLocal() as session:
        session.add(obj)
        await session.flush()
        reference = MediaImportReference(
            object_id=obj.id,
            filename="blocked.png",
            normalized_filename="blocked.png",
        )
        session.add(reference)
        await session.commit()
        reference_id = reference.id

    job_dir = tmp_path / "malformed-job"
    images_dir = job_dir / "images"
    images_dir.mkdir(parents=True)
    Image.new("RGB", (1, 1)).save(images_dir / "blocked.png")
    (job_dir / "mapping.csv").write_text("foo,bar\nx,y\n", encoding="utf-8")
    monkeypatch.setattr(settings, "media_root", str(tmp_path / "malformed-media"))
    monkeypatch.setattr(generate_iiif_tiles, "delay", lambda *args, **kwargs: None)

    result = await _import_media_batch(uuid.uuid4(), job_dir, MagicMock())

    assert result["created"] == 0
    assert result["report"]["errors"]
    async with AsyncSessionLocal() as session:
        assert await session.get(MediaImportReference, reference_id) is not None
