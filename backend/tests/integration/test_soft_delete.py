# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import asyncio
import threading
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select


class _FakeRedis:
    """Stand-in for redis.from_url in bulk_reindex_type_task's lock — no broker
    is available in the integration test environment (see tests/test_index_tasks.py
    for the same fake used at the unit-test level)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def lock(self, _name, **_kwargs):
        return self._lock

    def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_object_soft_delete_listed_in_trash_and_restorable(
    async_client, auth_headers
) -> None:
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
@pytest.mark.parametrize(
    ("record_type", "endpoint", "payload_factory"),
    [
        (
            "object",
            "/v1/objects",
            lambda idno: {"idno": idno, "status": "draft", "metadata_": {"label": "to be trashed"}},
        ),
        (
            "entity",
            "/v1/entities",
            lambda idno: {
                "idno": idno,
                "entity_type": "person",
                "status": "draft",
                "metadata_": {"label": "to be trashed"},
            },
        ),
        (
            "place",
            "/v1/places",
            lambda idno: {"idno": idno, "status": "draft", "metadata_": {"label": "to be trashed"}},
        ),
        (
            "occurrence",
            "/v1/occurrences",
            lambda idno: {"idno": idno, "status": "draft", "metadata_": {"label": "to be trashed"}},
        ),
        (
            "collection",
            "/v1/collections",
            lambda idno: {"idno": idno, "status": "draft", "metadata_": {"label": "to be trashed"}},
        ),
        (
            "storage_location",
            "/v1/storage-locations",
            lambda idno: {"idno": idno, "metadata_": {"label": "to be trashed"}},
        ),
    ],
    ids=["object", "entity", "place", "occurrence", "collection", "storage_location"],
)
async def test_record_soft_delete_and_restore_all_six_types(
    async_client, auth_headers, record_type: str, endpoint: str, payload_factory
) -> None:
    idno = f"TRASH-{record_type.upper()[:4]}-{uuid.uuid4().hex[:10]}"
    created = await async_client.post(
        endpoint,
        headers=auth_headers,
        json=payload_factory(idno),
    )
    assert created.status_code == 201, created.text
    record_id = created.json()["id"]

    delete_response = await async_client.delete(f"{endpoint}/{record_id}", headers=auth_headers)
    assert delete_response.status_code == 204

    missing = await async_client.get(f"{endpoint}/{record_id}", headers=auth_headers)
    assert missing.status_code == 404

    trash = await async_client.get(f"{endpoint}/trash/list", headers=auth_headers)
    assert trash.status_code == 200
    assert any(item["id"] == record_id for item in trash.json())

    restored = await async_client.post(f"{endpoint}/{record_id}/restore", headers=auth_headers)
    assert restored.status_code == 200, restored.text
    assert restored.json()["deleted_at"] is None

    visible_again = await async_client.get(f"{endpoint}/{record_id}", headers=auth_headers)
    assert visible_again.status_code == 200

    trash_after_restore = await async_client.get(f"{endpoint}/trash/list", headers=auth_headers)
    assert not any(item["id"] == record_id for item in trash_after_restore.json())

    audit = await async_client.get(f"{endpoint}/{record_id}/audit-log", headers=auth_headers)
    assert audit.status_code == 200, audit.text
    actions = [entry["action"] for entry in audit.json()]
    assert "delete" in actions
    assert "undelete" in actions


@pytest.mark.asyncio
async def test_soft_delete_and_restore_preserve_generic_and_metadata_relations(
    async_client, auth_headers
) -> None:
    import katalon.database as database_module
    from katalon.core.models import Entity, FieldDefinition, Relation

    target = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"REL-TARGET-{uuid.uuid4().hex[:12]}",
            "status": "draft",
            "metadata_": {"label": "target"},
        },
    )
    assert target.status_code == 201, target.text
    target_id = uuid.UUID(target.json()["id"])
    field_name = f"purge_preserve_{uuid.uuid4().hex[:8]}"
    async with database_module.AsyncSessionLocal() as session:
        session.add(
            FieldDefinition(
                target_type="entity",
                name=field_name,
                label={"de": "Bezug"},
                field_type="relation",
                settings={"target_type": "object"},
            )
        )
        source = Entity(
            idno=f"REL-SOURCE-{uuid.uuid4().hex[:12]}",
            entity_type="person",
            status="draft",
            metadata_={field_name: {"id": str(target_id), "label": "target"}},
        )
        session.add(source)
        await session.flush()
        source_id = source.id
        session.add(
            Relation(
                from_type="entity",
                from_id=source_id,
                to_type="object",
                to_id=target_id,
                relation_type="references",
            )
        )
        await session.commit()

    deleted = await async_client.delete(f"/v1/objects/{target_id}?force=true", headers=auth_headers)
    assert deleted.status_code == 204, deleted.text
    async with database_module.AsyncSessionLocal() as session:
        source = await session.get(Entity, source_id)
        assert source.metadata_[field_name]["id"] == str(target_id)
        assert (
            await session.execute(
                select(Relation).where(Relation.from_id == source_id, Relation.to_id == target_id)
            )
        ).scalar_one_or_none() is not None

    restored = await async_client.post(f"/v1/objects/{target_id}/restore", headers=auth_headers)
    assert restored.status_code == 200, restored.text
    async with database_module.AsyncSessionLocal() as session:
        source = await session.get(Entity, source_id)
        assert source.metadata_[field_name]["id"] == str(target_id)
        assert (
            await session.execute(
                select(Relation).where(Relation.from_id == source_id, Relation.to_id == target_id)
            )
        ).scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_soft_delete_rollback_leaves_record_active_and_relations_intact(
    async_client, auth_headers, monkeypatch
) -> None:
    """A soft delete occurring in an aborted / rolled back transaction leaves the record
    active (deleted_at is None) and leaves both incoming and outgoing relations
    and metadata references untouched (#398)."""
    import katalon.database as database_module
    from katalon.core.models import AuditLog, Entity, FieldDefinition, Object, Relation

    # 1. Create target object
    target = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"ROLL-TARGET-{uuid.uuid4().hex[:10]}",
            "status": "draft",
            "metadata_": {"label": "target object"},
        },
    )
    assert target.status_code == 201, target.text
    target_id = uuid.UUID(target.json()["id"])

    # 2. Create destination place for outgoing relation from target
    dest = await async_client.post(
        "/v1/places",
        headers=auth_headers,
        json={
            "idno": f"ROLL-DEST-{uuid.uuid4().hex[:10]}",
            "status": "draft",
            "metadata_": {"label": "destination place"},
        },
    )
    assert dest.status_code == 201, dest.text
    dest_id = uuid.UUID(dest.json()["id"])

    # 3. Create relation field definitions and source entity for incoming relation
    incoming_field = f"rel_in_{uuid.uuid4().hex[:8]}"
    outgoing_field = f"rel_out_{uuid.uuid4().hex[:8]}"

    async with database_module.AsyncSessionLocal() as session:
        session.add(
            FieldDefinition(
                target_type="entity",
                name=incoming_field,
                label={"de": "Bezug Objekt"},
                field_type="relation",
                settings={"target_type": "object"},
            )
        )
        session.add(
            FieldDefinition(
                target_type="object",
                name=outgoing_field,
                label={"de": "Bezug Ort"},
                field_type="relation",
                settings={"target_type": "place"},
            )
        )

        source = Entity(
            idno=f"ROLL-SRC-{uuid.uuid4().hex[:10]}",
            entity_type="person",
            status="draft",
            metadata_={incoming_field: {"id": str(target_id), "label": "target"}},
        )
        session.add(source)
        await session.flush()
        source_id = source.id

        # Update target with outgoing metadata reference
        target_obj = await session.get(Object, target_id)
        target_obj.metadata_ = {
            **target_obj.metadata_,
            outgoing_field: {"id": str(dest_id), "label": "place"},
        }

        # Incoming relation: Entity -> Object
        session.add(
            Relation(
                from_type="entity",
                from_id=source_id,
                to_type="object",
                to_id=target_id,
                relation_type="references",
            )
        )
        # Outgoing relation: Object -> Place
        session.add(
            Relation(
                from_type="object",
                from_id=target_id,
                to_type="place",
                to_id=dest_id,
                relation_type="located_at",
            )
        )
        await session.commit()

    # 4. Attempt a soft delete that fails mid-transaction:
    # Monkeypatch log_change to simulate an unhandled failure during delete,
    # causing the request transaction in get_db() to abort and roll back.
    async def _failing_log_change(*_args, **_kwargs):
        raise RuntimeError("Simulated failure during soft delete")

    monkeypatch.setattr("katalon.api.v1.objects.log_change", _failing_log_change)

    try:
        response = await async_client.delete(
            f"/v1/objects/{target_id}?force=true", headers=auth_headers
        )
        assert response.status_code >= 500
    except RuntimeError as exc:
        assert "Simulated failure during soft delete" in str(exc)

    # 5. Verify the rollback state:
    # a) Target record remains active (deleted_at is None) and retrievable via GET
    get_res = await async_client.get(f"/v1/objects/{target_id}", headers=auth_headers)
    assert get_res.status_code == 200
    assert get_res.json()["deleted_at"] is None

    trash_res = await async_client.get("/v1/objects/trash/list", headers=auth_headers)
    assert not any(item["id"] == str(target_id) for item in trash_res.json())

    # b) Incoming relation and metadata reference on source entity are completely untouched
    async with database_module.AsyncSessionLocal() as session:
        src = await session.get(Entity, source_id)
        assert src.metadata_[incoming_field]["id"] == str(target_id)
        in_rel_after = (
            await session.execute(
                select(Relation).where(Relation.from_id == source_id, Relation.to_id == target_id)
            )
        ).scalar_one_or_none()
        assert in_rel_after is not None

        # c) Outgoing relation and metadata reference on target object are completely untouched
        tgt = await session.get(Object, target_id)
        assert tgt.metadata_[outgoing_field]["id"] == str(dest_id)
        assert tgt.deleted_at is None
        out_rel_after = (
            await session.execute(
                select(Relation).where(Relation.from_id == target_id, Relation.to_id == dest_id)
            )
        ).scalar_one_or_none()
        assert out_rel_after is not None

        # d) No "delete" audit log entry was persisted for target
        delete_audit = (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.record_id == target_id,
                    AuditLog.action == "delete",
                )
            )
        ).scalar_one_or_none()
        assert delete_audit is None


@pytest.mark.asyncio
async def test_soft_delete_session_rollback_leaves_record_active_and_relations_intact(
    async_client, auth_headers
) -> None:
    """Explicit database session rollback after soft-delete leaves record and relations untouched."""
    import katalon.database as database_module
    from katalon.core.models import Entity, FieldDefinition, Object, Relation

    target = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"TX-TARGET-{uuid.uuid4().hex[:10]}",
            "status": "draft",
            "metadata_": {"label": "tx target"},
        },
    )
    assert target.status_code == 201, target.text
    target_id = uuid.UUID(target.json()["id"])
    field_name = f"tx_rel_{uuid.uuid4().hex[:8]}"

    async with database_module.AsyncSessionLocal() as session:
        session.add(
            FieldDefinition(
                target_type="entity",
                name=field_name,
                label={"de": "Bezug"},
                field_type="relation",
                settings={"target_type": "object"},
            )
        )
        source = Entity(
            idno=f"TX-SRC-{uuid.uuid4().hex[:10]}",
            entity_type="person",
            status="draft",
            metadata_={field_name: {"id": str(target_id), "label": "tx target"}},
        )
        session.add(source)
        await session.flush()
        source_id = source.id
        session.add(
            Relation(
                from_type="entity",
                from_id=source_id,
                to_type="object",
                to_id=target_id,
                relation_type="references",
            )
        )
        await session.commit()

    # Perform soft-delete in a transaction that gets rolled back
    async with database_module.AsyncSessionLocal() as session:
        obj = await session.get(Object, target_id)
        assert obj is not None
        obj.deleted_at = datetime.now(UTC).replace(tzinfo=None)
        await session.flush()
        await session.rollback()

    # Target is still active and relations are intact
    async with database_module.AsyncSessionLocal() as session:
        obj_after = await session.get(Object, target_id)
        assert obj_after.deleted_at is None
        source_after = await session.get(Entity, source_id)
        assert source_after.metadata_[field_name]["id"] == str(target_id)
        rel_after = (
            await session.execute(
                select(Relation).where(Relation.from_id == source_id, Relation.to_id == target_id)
            )
        ).scalar_one_or_none()
        assert rel_after is not None

    get_check = await async_client.get(f"/v1/objects/{target_id}", headers=auth_headers)
    assert get_check.status_code == 200


@pytest.mark.asyncio
async def test_deleted_public_object_returns_tombstone_for_anonymous(
    async_client, auth_headers
) -> None:
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

    archived = await async_client.post(
        f"/v1/procedures/{procedure_id}/archive", headers=auth_headers
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["status"] == "archived"

    still_there = await async_client.get(f"/v1/procedures/{procedure_id}", headers=auth_headers)
    assert still_there.status_code == 200
    assert still_there.json()["status"] == "archived"


def test_procedure_has_no_soft_delete() -> None:
    """Procedures deliberately have no soft-delete column / lifecycle (#398)."""
    from katalon.core.models import Procedure
    from katalon.core.schemas import ProcedureCreate, ProcedureRead

    assert hasattr(Procedure, "deleted_at") is False
    assert "deleted_at" not in Procedure.__table__.columns
    assert "deleted_at" not in ProcedureCreate.model_fields
    assert "deleted_at" not in ProcedureRead.model_fields


@pytest.mark.asyncio
async def test_procedure_delete_is_hard_delete_without_trash_or_restore(
    async_client, auth_headers
) -> None:
    """Procedures use hard delete (or archiving), not soft delete (#398)."""
    import katalon.database as database_module
    from katalon.core.models import Procedure

    created = await async_client.post(
        "/v1/procedures",
        headers=auth_headers,
        json={
            "idno": f"PROC-HARD-{uuid.uuid4().hex[:12]}",
            "procedure_type": "loan_out",
            "status": "draft",
            "metadata_": {},
        },
    )
    assert created.status_code == 201, created.text
    proc_id = uuid.UUID(created.json()["id"])

    # Hard delete procedure
    del_res = await async_client.delete(f"/v1/procedures/{proc_id}", headers=auth_headers)
    assert del_res.status_code == 204

    # Row is completely deleted from DB, not soft-deleted
    async with database_module.AsyncSessionLocal() as session:
        proc_in_db = await session.get(Procedure, proc_id)
        assert proc_in_db is None

    # Procedure has no trash endpoint (returns 404 or 405)
    trash_res = await async_client.get("/v1/procedures/trash/list", headers=auth_headers)
    assert trash_res.status_code in (404, 405)

    # Procedure has no restore endpoint (returns 404 or 405)
    restore_res = await async_client.post(f"/v1/procedures/{proc_id}/restore", headers=auth_headers)
    assert restore_res.status_code in (404, 405)


@pytest.mark.asyncio
async def test_purge_task_hard_deletes_past_retention_window(
    async_client, auth_headers, monkeypatch, tmp_path
) -> None:
    import katalon.database as database_module
    from katalon.core.media_storage import storage_path
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
    media_root = tmp_path / "media"
    monkeypatch.setattr("katalon.config.settings.media_root", str(media_root))
    media_path = media_root / "ab" / "purge-me.jpg"
    media_path.parent.mkdir(parents=True)
    media_path.write_bytes(b"fake-image-bytes")
    assert storage_path("ab/purge-me.jpg") == media_path
    async with database_module.AsyncSessionLocal() as session:
        session.add(
            MediaFile(
                object_id=uuid.UUID(object_id),
                filename="purge-me.jpg",
                mime_type="image/jpeg",
                storage_key="ab/purge-me.jpg",
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

    monkeypatch.setattr("katalon.integrations.elasticsearch.count_by_type", _fake_count_by_type)
    monkeypatch.setattr(
        "katalon.integrations.elasticsearch.list_ids_by_type", _fake_list_ids_by_type
    )

    report = await asyncio.to_thread(
        index_tasks.reconciliation_job_task, mode="id_diff", force=True
    )
    assert object_id not in [rid for _, rid in dispatched]
    assert report["object"]["mode"] == "id_diff"


@pytest.mark.asyncio
async def test_bulk_reindex_and_reindex_all_skip_soft_deleted(
    async_client, auth_headers, monkeypatch
) -> None:
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
    reindexed_types: list[str] = []

    async def _fake_reindex_type(record_type: str, records: list) -> int:
        reindexed_types.append(record_type)
        indexed.extend(rid for rid, _ in records)
        return len(records)

    monkeypatch.setattr("katalon.integrations.elasticsearch.reindex_type", _fake_reindex_type)
    monkeypatch.setattr("redis.from_url", lambda *_args, **_kwargs: _FakeRedis())
    report = await asyncio.to_thread(index_tasks.bulk_reindex_type_task, "object")
    assert object_id not in indexed
    assert report["status"] == "ok"

    indexed.clear()
    reindexed_types.clear()
    await asyncio.to_thread(index_tasks.reindex_all_task)
    assert object_id not in indexed
    assert reindexed_types == [
        "object",
        "entity",
        "place",
        "occurrence",
        "procedure",
        "collection",
        "storage_location",
    ]
