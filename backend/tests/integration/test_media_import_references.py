import asyncio
import uuid
from unittest.mock import MagicMock

import pytest
from PIL import Image
from sqlalchemy import select

from katalon.core.models import MediaImportReference, Object


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

    result = await asyncio.to_thread(
        import_records_task.run,
        "object",
        [{"recordID": idno, "resourceID": ["Vorne.JPG", "Hinten.jpg"]}],
        {"recordID": "__idno__"},
        upsert_strategy="skip",
        media_selector="resourceID",
    )

    assert result["skipped"] == 1
    assert result["media_references_created"] == 2
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
    async with AsyncSessionLocal() as session:
        assert await session.get(MediaImportReference, good_reference_id) is None
        assert await session.get(MediaImportReference, bad_reference_id) is not None
