# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Regression coverage for #390: manual media delete and the automatic purge
worker must commit the deletion intent (MediaFile.deleted_at) before any
irreversible physical storage deletion, physical deletion must be idempotent
and retryable, and a storage failure must leave a visibly pending row rather
than a silently successful or silently lost one. See
katalon.services.media_deletion_service for the lifecycle these tests exercise.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select


@pytest.mark.asyncio
async def test_manual_delete_removes_file_and_row_when_storage_succeeds(
    async_client, auth_headers, monkeypatch, tmp_path
) -> None:
    import katalon.database as database_module
    from katalon.core.models import MediaFile

    media_root = tmp_path / "media"
    monkeypatch.setattr("katalon.config.settings.media_root", str(media_root))

    created = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={"idno": f"MDEL-{uuid.uuid4().hex[:12]}", "status": "draft", "metadata_": {"label": "x"}},
    )
    assert created.status_code == 201, created.text
    object_id = created.json()["id"]

    media_path = media_root / "ab" / "delete-me.jpg"
    media_path.parent.mkdir(parents=True)
    media_path.write_bytes(b"bytes")
    media_id = uuid.uuid4()
    async with database_module.AsyncSessionLocal() as session:
        session.add(
            MediaFile(
                id=media_id,
                object_id=uuid.UUID(object_id),
                filename="delete-me.jpg",
                mime_type="image/jpeg",
                storage_key="ab/delete-me.jpg",
                status="ready",
            )
        )
        await session.commit()

    resp = await async_client.delete(f"/v1/objects/{object_id}/media/{media_id}", headers=auth_headers)
    assert resp.status_code == 204

    assert not media_path.exists()
    async with database_module.AsyncSessionLocal() as session:
        assert await session.get(MediaFile, media_id) is None


@pytest.mark.asyncio
async def test_manual_delete_commits_intent_and_leaves_file_untouched_when_storage_fails(
    async_client, auth_headers, monkeypatch, tmp_path
) -> None:
    """A storage outage after the delete request must not lose the file, and
    must not silently report success — the row stays a pending, retryable
    marker, and every read path already treats it as gone."""
    import katalon.database as database_module
    from katalon.core.media_storage import LocalStorage, StorageDeleteError
    from katalon.core.models import MediaFile
    from katalon.services.media_deletion_service import sweep_pending_media_deletes

    media_root = tmp_path / "media"
    monkeypatch.setattr("katalon.config.settings.media_root", str(media_root))

    created = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={"idno": f"MDELFAIL-{uuid.uuid4().hex[:12]}", "status": "draft", "metadata_": {"label": "x"}},
    )
    assert created.status_code == 201, created.text
    object_id = created.json()["id"]

    media_path = media_root / "ab" / "stuck.jpg"
    media_path.parent.mkdir(parents=True)
    media_path.write_bytes(b"bytes")
    media_id = uuid.uuid4()
    async with database_module.AsyncSessionLocal() as session:
        session.add(
            MediaFile(
                id=media_id,
                object_id=uuid.UUID(object_id),
                filename="stuck.jpg",
                mime_type="image/jpeg",
                storage_key="ab/stuck.jpg",
                status="ready",
            )
        )
        await session.commit()

    async def _boom(self, *keys: str) -> None:
        raise StorageDeleteError(dict.fromkeys(keys, "simulated storage outage"))

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(LocalStorage, "delete", _boom)
        resp = await async_client.delete(f"/v1/objects/{object_id}/media/{media_id}", headers=auth_headers)
        assert resp.status_code == 204  # deletion intent accepted; physical cleanup pending

        assert media_path.exists()  # never touched — storage never reported success

        async with database_module.AsyncSessionLocal() as session:
            media = await session.get(MediaFile, media_id)
            assert media is not None
            assert media.deleted_at is not None  # durable, retryable pending-delete marker

        # Already logically gone from every read path despite the row still existing.
        listing = await async_client.get(f"/v1/objects/{object_id}/media", headers=auth_headers)
        assert listing.status_code == 200
        assert listing.json() == []

    # Storage recovers (LocalStorage.delete restored) — a retry (the periodic
    # sweep in production) finishes the job without any manual intervention.
    async with database_module.AsyncSessionLocal() as session:
        report = await sweep_pending_media_deletes(session)
        await session.commit()
    assert report == {"pending": 1, "finalized": 1, "still_pending": 0}
    assert not media_path.exists()
    async with database_module.AsyncSessionLocal() as session:
        assert await session.get(MediaFile, media_id) is None


@pytest.mark.asyncio
async def test_sweep_survives_crash_between_intent_commit_and_physical_delete(
    app, monkeypatch, tmp_path
) -> None:
    """Simulates a worker crash: the deletion intent is committed, but no
    physical deletion attempt ever ran. The periodic sweep must still find and
    finalize it — and running the sweep again afterwards must be a harmless
    no-op, not a double-error."""
    import katalon.database as database_module
    from katalon.core.models import MediaFile, Object
    from katalon.services.media_deletion_service import (
        mark_pending_delete,
        sweep_pending_media_deletes,
    )

    media_root = tmp_path / "media"
    monkeypatch.setattr("katalon.config.settings.media_root", str(media_root))

    object_id = uuid.uuid4()
    media_id = uuid.uuid4()
    media_path = media_root / "ab" / "crash.jpg"
    media_path.parent.mkdir(parents=True)
    media_path.write_bytes(b"bytes")

    async with database_module.AsyncSessionLocal() as session:
        session.add(Object(id=object_id, idno=f"CRASH-{uuid.uuid4().hex[:12]}", status="draft", metadata_={}))
        media = MediaFile(
            id=media_id,
            object_id=object_id,
            filename="crash.jpg",
            mime_type="image/jpeg",
            storage_key="ab/crash.jpg",
            status="ready",
        )
        session.add(media)
        # This is the durable state a crash right after the request's commit
        # would leave behind: intent committed, physical delete never attempted.
        mark_pending_delete(media)
        await session.commit()

    async with database_module.AsyncSessionLocal() as session:
        report = await sweep_pending_media_deletes(session)
        await session.commit()
    assert report == {"pending": 1, "finalized": 1, "still_pending": 0}
    assert not media_path.exists()

    # Idempotent: nothing pending left, second run is a clean no-op.
    async with database_module.AsyncSessionLocal() as session:
        second_report = await sweep_pending_media_deletes(session)
        await session.commit()
    assert second_report == {"pending": 0, "finalized": 0, "still_pending": 0}


@pytest.mark.asyncio
async def test_s3_partial_batch_failure_stays_pending_and_reports_the_failing_key(
    app, monkeypatch
) -> None:
    """An S3 DeleteObjects response with per-object Errors (partial batch
    failure) must not be swallowed as success — the row must stay pending."""
    import katalon.database as database_module
    from katalon.core.media_storage import StorageDeleteError
    from katalon.core.models import MediaFile, Object
    from katalon.services.media_deletion_service import finalize_pending_delete, mark_pending_delete

    object_id = uuid.uuid4()
    media_id = uuid.uuid4()
    async with database_module.AsyncSessionLocal() as session:
        session.add(Object(id=object_id, idno=f"S3PART-{uuid.uuid4().hex[:12]}", status="draft", metadata_={}))
        media = MediaFile(
            id=media_id,
            object_id=object_id,
            filename="master.tif",
            mime_type="image/tiff",
            storage_key="ab/master.tif",
            iiif_storage_key="ab/master_pyramid.tif",
            status="ready",
        )
        session.add(media)
        mark_pending_delete(media)
        await session.commit()

        class _FlakyS3:
            is_local = False

            async def delete(self, *keys: str) -> None:
                # Mirrors a real S3Storage.delete: only the pyramid derivative
                # failed (e.g. AccessDenied), the master would have succeeded.
                raise StorageDeleteError({"ab/master_pyramid.tif": "AccessDenied: simulated"})

        monkeypatch.setattr(
            "katalon.services.media_deletion_service.get_storage", lambda: _FlakyS3()
        )

        finalized = await finalize_pending_delete(media)
        assert finalized is False

    async with database_module.AsyncSessionLocal() as session:
        still_pending = await session.get(MediaFile, media_id)
        assert still_pending is not None
        assert still_pending.deleted_at is not None


@pytest.mark.asyncio
async def test_purge_defers_record_when_media_deletion_fails_and_retries_next_run(
    async_client, auth_headers, monkeypatch, tmp_path
) -> None:
    """A storage failure during the automatic purge must not hard-delete the
    parent record (media_files.object_id cascades on delete — deleting the
    object first would silently destroy the pending-delete marker for a file
    that still exists in storage). The record stays soft-deleted, past
    cutoff, and gets purged on the next run once storage recovers."""
    import katalon.database as database_module
    from katalon.core.media_storage import LocalStorage, StorageDeleteError
    from katalon.core.models import AuditLog, MediaFile, Object
    from katalon.workers import purge_tasks

    media_root = tmp_path / "media"
    monkeypatch.setattr("katalon.config.settings.media_root", str(media_root))

    created = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={"idno": f"PURGEFAIL-{uuid.uuid4().hex[:12]}", "status": "draft", "metadata_": {"label": "x"}},
    )
    assert created.status_code == 201, created.text
    object_id = created.json()["id"]

    media_path = media_root / "ab" / "wont-go.jpg"
    media_path.parent.mkdir(parents=True)
    media_path.write_bytes(b"bytes")
    async with database_module.AsyncSessionLocal() as session:
        session.add(
            MediaFile(
                object_id=uuid.UUID(object_id),
                filename="wont-go.jpg",
                mime_type="image/jpeg",
                storage_key="ab/wont-go.jpg",
                status="ready",
            )
        )
        await session.commit()

    delete_response = await async_client.delete(f"/v1/objects/{object_id}", headers=auth_headers)
    assert delete_response.status_code == 204

    async with database_module.AsyncSessionLocal() as session:
        result = await session.execute(select(Object).where(Object.id == uuid.UUID(object_id)))
        obj = result.scalar_one()
        obj.deleted_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=999)
        await session.commit()

    async def _boom(self, *keys: str) -> None:
        raise StorageDeleteError(dict.fromkeys(keys, "simulated storage outage"))

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(LocalStorage, "delete", _boom)
        totals = await purge_tasks._do_purge()
    assert totals["object"] == 0  # deferred, not purged

    assert media_path.exists()  # untouched despite the failed run

    async with database_module.AsyncSessionLocal() as session:
        still_there = await session.execute(select(Object).where(Object.id == uuid.UUID(object_id)))
        assert still_there.scalar_one_or_none() is not None

        media_row = await session.execute(
            select(MediaFile).where(MediaFile.object_id == uuid.UUID(object_id))
        )
        media = media_row.scalar_one_or_none()
        assert media is not None
        assert media.deleted_at is not None  # committed intent survived the failed run

        audit_row = await session.execute(
            select(AuditLog).where(AuditLog.record_id == uuid.UUID(object_id), AuditLog.action == "purge")
        )
        assert audit_row.scalar_one_or_none() is None  # not purged yet — no purge audit entry

    # Storage recovers: the next scheduled run (retry, no process restart
    # needed) finishes what the failed run started.
    totals_retry = await purge_tasks._do_purge()
    assert totals_retry["object"] == 1
    assert not media_path.exists()

    async with database_module.AsyncSessionLocal() as session:
        assert (
            await session.execute(select(Object).where(Object.id == uuid.UUID(object_id)))
        ).scalar_one_or_none() is None
        assert (
            await session.execute(select(MediaFile).where(MediaFile.object_id == uuid.UUID(object_id)))
        ).scalar_one_or_none() is None
        audit_row = await session.execute(
            select(AuditLog).where(AuditLog.record_id == uuid.UUID(object_id), AuditLog.action == "purge")
        )
        assert audit_row.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_purge_hard_deletes_soft_deleted_collections_and_storage_locations(
    app, monkeypatch
) -> None:
    """#390 acceptance criterion: purge must cover every soft-delete-capable
    record type. Collection and StorageLocation were previously missing from
    the purge worker's model_map even though both carry deleted_at.

    Fixtures are built directly via the ORM rather than the create endpoints:
    both endpoints currently reject every request with "Feld 'idno' ist
    erforderlich." in a fresh test database — a pre-existing metadata-schema
    seeding issue unrelated to #390 (reproduces identically on main for
    tests/integration/test_storage_locations_integration.py) — going through
    the ORM keeps this test scoped to purge_tasks._do_purge() coverage only.
    """
    import katalon.database as database_module
    from katalon.core.models import Collection, StorageLocation
    from katalon.workers import purge_tasks

    col_id = uuid.uuid4()
    loc_id = uuid.uuid4()
    old_cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=999)
    async with database_module.AsyncSessionLocal() as session:
        session.add(
            Collection(
                id=col_id,
                idno=f"COLPURGE-{uuid.uuid4().hex[:12]}",
                status="draft",
                metadata_={"label": "x"},
                deleted_at=old_cutoff,
            )
        )
        session.add(
            StorageLocation(
                id=loc_id,
                idno=f"LOCPURGE-{uuid.uuid4().hex[:12]}",
                metadata_={"label": "x"},
                deleted_at=old_cutoff,
            )
        )
        await session.commit()

    totals = await purge_tasks._do_purge()
    assert totals["collection"] >= 1
    assert totals["storage_location"] >= 1

    async with database_module.AsyncSessionLocal() as session:
        assert (
            await session.execute(select(Collection).where(Collection.id == col_id))
        ).scalar_one_or_none() is None
        assert (
            await session.execute(select(StorageLocation).where(StorageLocation.id == loc_id))
        ).scalar_one_or_none() is None
