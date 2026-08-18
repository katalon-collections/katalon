import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select


@pytest.mark.asyncio
async def test_object_soft_delete_listed_in_trash_and_restorable(async_client, auth_headers) -> None:
    created = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"TRASH-{uuid.uuid4().hex[:12]}",
            "status": "draft",
            "metadata_": {"label": "to be trashed"},
        },
    )
    assert created.status_code == 201, created.text
    object_id = created.json()["id"]

    delete_response = await async_client.delete(f"/v1/objects/{object_id}", headers=auth_headers)
    assert delete_response.status_code == 204

    missing = await async_client.get(f"/v1/objects/{object_id}", headers=auth_headers)
    assert missing.status_code == 404

    trash = await async_client.get("/v1/objects/trash/list", headers=auth_headers)
    assert trash.status_code == 200
    assert any(item["id"] == object_id for item in trash.json())

    restored = await async_client.post(f"/v1/objects/{object_id}/restore", headers=auth_headers)
    assert restored.status_code == 200, restored.text
    assert restored.json()["deleted_at"] is None

    visible_again = await async_client.get(f"/v1/objects/{object_id}", headers=auth_headers)
    assert visible_again.status_code == 200

    trash_after_restore = await async_client.get("/v1/objects/trash/list", headers=auth_headers)
    assert not any(item["id"] == object_id for item in trash_after_restore.json())

    audit = await async_client.get(f"/v1/objects/{object_id}/audit-log", headers=auth_headers)
    actions = [entry["action"] for entry in audit.json()]
    assert "delete" in actions
    assert "undelete" in actions


@pytest.mark.asyncio
async def test_deleted_public_object_returns_tombstone_for_anonymous(async_client, auth_headers) -> None:
    import katalon.database as database_module
    from katalon.core.models import Object

    idno = f"TOMB-{uuid.uuid4().hex[:12]}"
    created = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={"idno": idno, "status": "draft", "metadata_": {"label": "public record"}},
    )
    object_id = created.json()["id"]

    # Set status directly to sidestep publish-field validation (irrelevant to this test,
    # and other test modules leave required field_definitions behind in the shared DB).
    async with database_module.AsyncSessionLocal() as session:
        result = await session.execute(select(Object).where(Object.id == uuid.UUID(object_id)))
        obj = result.scalar_one()
        obj.status = "public"
        await session.commit()

    anon_before_delete = await async_client.get(f"/portal/v1/objects/{object_id}")
    assert anon_before_delete.status_code == 200

    delete_response = await async_client.delete(f"/v1/objects/{object_id}", headers=auth_headers)
    assert delete_response.status_code == 204

    anon_after_delete = await async_client.get(f"/portal/v1/objects/{object_id}")
    assert anon_after_delete.status_code == 410

    admin_after_delete = await async_client.get(f"/v1/objects/{object_id}", headers=auth_headers)
    assert admin_after_delete.status_code == 404


@pytest.mark.asyncio
async def test_procedure_archive_flips_status_without_deleting(async_client, auth_headers) -> None:
    created = await async_client.post(
        "/v1/procedures",
        headers=auth_headers,
        json={
            "idno": f"PROC-{uuid.uuid4().hex[:12]}",
            "procedure_type": "loan_out",
            "status": "draft",
            "metadata_": {},
        },
    )
    assert created.status_code == 201, created.text
    procedure_id = created.json()["id"]

    archived = await async_client.post(f"/v1/procedures/{procedure_id}/archive", headers=auth_headers)
    assert archived.status_code == 200, archived.text
    assert archived.json()["status"] == "archived"

    still_there = await async_client.get(f"/v1/procedures/{procedure_id}", headers=auth_headers)
    assert still_there.status_code == 200
    assert still_there.json()["status"] == "archived"


@pytest.mark.asyncio
async def test_purge_task_hard_deletes_past_retention_window(async_client, auth_headers, monkeypatch, tmp_path) -> None:
    import katalon.database as database_module
    from katalon.core.models import AuditLog, MediaFile, Object
    from katalon.workers import purge_tasks

    created = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"PURGE-{uuid.uuid4().hex[:12]}",
            "status": "draft",
            "metadata_": {"label": "old trash"},
        },
    )
    object_id = created.json()["id"]

    # Attach a real on-disk media file — this is also the regression case for the
    # media_files.object_id NOT NULL cascade bug (fixed via passive_deletes=True):
    # purge is now where an object row actually gets hard-deleted.
    media_path = tmp_path / "purge-me.jpg"
    media_path.write_bytes(b"fake-image-bytes")
    async with database_module.AsyncSessionLocal() as session:
        session.add(
            MediaFile(
                object_id=uuid.UUID(object_id),
                filename="purge-me.jpg",
                mime_type="image/jpeg",
                file_path=str(media_path),
                status="ready",
            )
        )
        await session.commit()

    delete_response = await async_client.delete(f"/v1/objects/{object_id}", headers=auth_headers)
    assert delete_response.status_code == 204

    # Backdate deleted_at past the retention window so the purge job picks it up.
    async with database_module.AsyncSessionLocal() as session:
        result = await session.execute(select(Object).where(Object.id == uuid.UUID(object_id)))
        obj = result.scalar_one()
        obj.deleted_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=999)
        await session.commit()

    monkeypatch.setattr("katalon.config.settings.purge_after_days", 30)
    totals = await purge_tasks._do_purge()
    assert totals["object"] >= 1

    assert not media_path.exists()

    async with database_module.AsyncSessionLocal() as session:
        result = await session.execute(select(Object).where(Object.id == uuid.UUID(object_id)))
        assert result.scalar_one_or_none() is None

        media_result = await session.execute(
            select(MediaFile).where(MediaFile.object_id == uuid.UUID(object_id))
        )
        assert media_result.scalar_one_or_none() is None

        audit_result = await session.execute(
            select(AuditLog).where(
                AuditLog.record_id == uuid.UUID(object_id), AuditLog.action == "purge"
            )
        )
        assert audit_result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_reconciliation_does_not_resurrect_soft_deleted_records(
    async_client, auth_headers, monkeypatch
) -> None:
    """ES reconciliation must not treat a soft-deleted (and thus deindexed) record as
    'missing from ES' and re-add it — that would defeat the tombstone entirely."""
    from katalon.workers import index_tasks

    created = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"RECON-{uuid.uuid4().hex[:12]}",
            "status": "draft",
            "metadata_": {"label": "should stay gone"},
        },
    )
    object_id = created.json()["id"]

    delete_response = await async_client.delete(f"/v1/objects/{object_id}", headers=auth_headers)
    assert delete_response.status_code == 204

    dispatched: list[tuple[str, str]] = []
    monkeypatch.setattr(
        index_tasks.index_record_dispatch_task,
        "delay",
        lambda record_type, record_id: dispatched.append((record_type, record_id)),
    )
    monkeypatch.setattr(index_tasks.remove_record_task, "delay", lambda record_id: None)

    async def _fake_count_by_type(record_type: str) -> int:
        return 0

    async def _fake_list_ids_by_type(record_type: str) -> set:
        return set()

    monkeypatch.setattr(
        "katalon.integrations.elasticsearch.count_by_type", _fake_count_by_type
    )
    monkeypatch.setattr(
        "katalon.integrations.elasticsearch.list_ids_by_type", _fake_list_ids_by_type
    )

    report = await asyncio.to_thread(index_tasks.reconciliation_job_task, mode="id_diff", force=True)
    assert object_id not in [rid for _, rid in dispatched]
    assert report["object"]["mode"] == "id_diff"


@pytest.mark.asyncio
async def test_bulk_reindex_and_reindex_all_skip_soft_deleted(async_client, auth_headers, monkeypatch) -> None:
    from katalon.workers import index_tasks

    created = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"BULK-{uuid.uuid4().hex[:12]}",
            "status": "draft",
            "metadata_": {"label": "should stay gone"},
        },
    )
    object_id = created.json()["id"]
    delete_response = await async_client.delete(f"/v1/objects/{object_id}", headers=auth_headers)
    assert delete_response.status_code == 204

    indexed: list[str] = []

    async def _fake_reindex_type(record_type: str, records: list) -> int:
        indexed.extend(rid for rid, _ in records)
        return len(records)

    monkeypatch.setattr("katalon.integrations.elasticsearch.reindex_type", _fake_reindex_type)
    report = await asyncio.to_thread(index_tasks.bulk_reindex_type_task, "object")
    assert object_id not in indexed
    assert report["status"] == "ok"

    async def _fake_ensure_index() -> None:
        return None

    async def _fake_index_document(record_id: str, doc: dict) -> None:
        indexed.append(record_id)

    monkeypatch.setattr("katalon.integrations.elasticsearch.ensure_index", _fake_ensure_index)
    monkeypatch.setattr("katalon.integrations.elasticsearch.index_document", _fake_index_document)
    await asyncio.to_thread(index_tasks.reindex_all_task)
    assert object_id not in indexed
