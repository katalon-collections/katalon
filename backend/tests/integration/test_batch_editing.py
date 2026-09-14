# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import asyncio
import uuid
from typing import Any

import pytest
from sqlalchemy import func, select

import katalon.database as database_module
from katalon.core.models import AuditLog, Object, Relation
from katalon.workers.batch_tasks import batch_edit_task


@pytest.fixture
def unique_suffix():
    return uuid.uuid4().hex[:12]


async def _create_object(
    async_client, auth_headers, idno: str, status: str = "draft", metadata: dict | None = None
):
    response = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": idno,
            "status": status,
            "metadata_": metadata or {},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_objects_bulk(
    count: int,
    prefix: str,
    status: str = "draft",
    metadata: dict[str, Any] | None = None,
) -> list[str]:
    ids = [str(uuid.uuid4()) for _ in range(count)]
    async with database_module.AsyncSessionLocal() as session:
        for i, obj_id in enumerate(ids):
            session.add(
                Object(
                    id=uuid.UUID(obj_id),
                    idno=f"{prefix}-{i}",
                    status=status,
                    collection_status="active",
                    metadata_=dict(metadata or {}),
                    ai_provenance={},
                )
            )
        await session.commit()
    return ids


async def _create_entity(
    async_client, auth_headers, idno: str, status: str = "draft", metadata: dict | None = None
):
    response = await async_client.post(
        "/v1/entities",
        headers=auth_headers,
        json={
            "idno": idno,
            "status": status,
            "metadata_": metadata or {},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_cataloger_user(
    async_client, auth_headers, unique_suffix: str
) -> tuple[str, dict[str, str]]:
    email = f"batch-cataloger-{unique_suffix}@katalon.dev"
    response = await async_client.post(
        "/v1/users",
        headers=auth_headers,
        json={"email": email, "password": "Cataloger1234", "role": "cataloger"},
    )
    assert response.status_code == 201, response.text
    user_id = response.json()["id"]
    token = await async_client.post(
        "/v1/auth/token",
        data={"username": email, "password": "Cataloger1234"},
    )
    assert token.status_code == 200, token.text
    return user_id, {"Authorization": f"Bearer {token.json()['access_token']}"}


async def _create_cataloger_headers(
    async_client, auth_headers, unique_suffix: str
) -> dict[str, str]:
    _, headers = await _create_cataloger_user(async_client, auth_headers, unique_suffix)
    return headers


@pytest.mark.asyncio
async def test_batch_set_status(async_client, auth_headers, unique_suffix):
    obj1 = await _create_object(async_client, auth_headers, f"BATCH-STATUS-1-{unique_suffix}")
    obj2 = await _create_object(async_client, auth_headers, f"BATCH-STATUS-2-{unique_suffix}")

    response = await async_client.post(
        "/v1/batch/object",
        headers=auth_headers,
        json={
            "ids": [obj1["id"], obj2["id"]],
            "operation": {"type": "set_status", "value": "public"},
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["affected"] == 2
    assert result["errors"] == []
    assert result["batch_job_id"] is not None

    for obj_id in (obj1["id"], obj2["id"]):
        obj = (await async_client.get(f"/v1/objects/{obj_id}", headers=auth_headers)).json()
        assert obj["status"] == "public"
        audit = (
            await async_client.get(f"/v1/objects/{obj_id}/audit-log", headers=auth_headers)
        ).json()
        assert any(entry["action"] == "batch_update" for entry in audit)
        assert any(
            entry.get("changed_fields", {}).get("batch_job_id") == result["batch_job_id"]
            for entry in audit
        )


@pytest.mark.asyncio
async def test_batch_set_field(async_client, auth_headers, unique_suffix):
    obj = await _create_object(
        async_client, auth_headers, f"BATCH-FIELD-{unique_suffix}", metadata={"label": "Before"}
    )

    response = await async_client.post(
        "/v1/batch/object",
        headers=auth_headers,
        json={
            "ids": [obj["id"]],
            "operation": {"type": "set_field", "field": "label", "value": "After"},
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["affected"] == 1
    assert result["errors"] == []

    updated = (await async_client.get(f"/v1/objects/{obj['id']}", headers=auth_headers)).json()
    assert updated["metadata_"]["label"] == "After"


@pytest.mark.asyncio
async def test_batch_append_and_clear_repeatable_field(async_client, auth_headers, unique_suffix):
    field_name = f"keywords_{unique_suffix}"
    schema_response = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "object",
            "name": field_name,
            "label": {"de": "Keywords"},
            "field_type": "text",
            "is_repeatable": True,
        },
    )
    assert schema_response.status_code == 201, schema_response.text

    obj = await _create_object(
        async_client,
        auth_headers,
        f"BATCH-APPEND-{unique_suffix}",
        metadata={field_name: ["alpha"]},
    )

    # Append
    response = await async_client.post(
        "/v1/batch/object",
        headers=auth_headers,
        json={
            "ids": [obj["id"]],
            "operation": {"type": "append_field", "field": field_name, "value": "beta"},
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["affected"] == 1

    updated = (await async_client.get(f"/v1/objects/{obj['id']}", headers=auth_headers)).json()
    assert updated["metadata_"][field_name] == ["alpha", "beta"]

    # Clear
    response = await async_client.post(
        "/v1/batch/object",
        headers=auth_headers,
        json={
            "ids": [obj["id"]],
            "operation": {"type": "clear_field", "field": field_name},
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["affected"] == 1

    updated = (await async_client.get(f"/v1/objects/{obj['id']}", headers=auth_headers)).json()
    assert updated["metadata_"].get(field_name) in (None, "", [])


@pytest.mark.asyncio
async def test_batch_add_and_remove_relation(async_client, auth_headers, unique_suffix):
    obj = await _create_object(async_client, auth_headers, f"BATCH-REL-OBJ-{unique_suffix}")
    entity = await _create_entity(async_client, auth_headers, f"BATCH-REL-ENT-{unique_suffix}")

    response = await async_client.post(
        "/v1/batch/object",
        headers=auth_headers,
        json={
            "ids": [obj["id"]],
            "operation": {
                "type": "add_relation",
                "relation_to_type": "entity",
                "relation_to_id": entity["id"],
                "relation_type": "related_to",
            },
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["affected"] == 1

    relations = (
        await async_client.get(
            "/v1/relations",
            headers=auth_headers,
            params={
                "from_type": "object",
                "from_id": obj["id"],
                "to_type": "entity",
                "to_id": entity["id"],
            },
        )
    ).json()
    assert len(relations) == 1
    assert relations[0]["relation_type"] == "related_to"

    # Remove
    response = await async_client.post(
        "/v1/batch/object",
        headers=auth_headers,
        json={
            "ids": [obj["id"]],
            "operation": {
                "type": "remove_relation",
                "relation_to_type": "entity",
                "relation_to_id": entity["id"],
                "relation_type": "related_to",
            },
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["affected"] == 1

    relations = (
        await async_client.get(
            "/v1/relations",
            headers=auth_headers,
            params={
                "from_type": "object",
                "from_id": obj["id"],
            },
        )
    ).json()
    assert relations == []


@pytest.mark.asyncio
async def test_batch_preserves_locked_fields_for_unprivileged_users(
    async_client, auth_headers, unique_suffix
):
    field_name = f"locked_{unique_suffix}"
    schema = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "object",
            "name": field_name,
            "label": {"de": "Locked"},
            "field_type": "text",
            "settings": {"is_locked": True},
        },
    )
    assert schema.status_code == 201, schema.text
    obj = await _create_object(
        async_client,
        auth_headers,
        f"BATCH-LOCKED-{unique_suffix}",
        metadata={field_name: "Original"},
    )
    cataloger_headers = await _create_cataloger_headers(async_client, auth_headers, unique_suffix)

    response = await async_client.post(
        "/v1/batch/object",
        headers=cataloger_headers,
        json={
            "ids": [obj["id"]],
            "operation": {"type": "set_field", "field": field_name, "value": "Changed"},
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["errors"] == []

    updated = (await async_client.get(f"/v1/objects/{obj['id']}", headers=auth_headers)).json()
    assert updated["metadata_"][field_name] == "Original"


@pytest.mark.asyncio
async def test_batch_rejects_missing_relation_target(async_client, auth_headers, unique_suffix):
    obj = await _create_object(async_client, auth_headers, f"BATCH-REL-MISSING-{unique_suffix}")

    response = await async_client.post(
        "/v1/batch/object",
        headers=auth_headers,
        json={
            "ids": [obj["id"]],
            "operation": {
                "type": "add_relation",
                "relation_to_type": "entity",
                "relation_to_id": str(uuid.uuid4()),
                "relation_type": "related_to",
            },
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["affected"] == 0
    assert "existiert nicht oder ist gelöscht" in result["errors"][0]


@pytest.mark.asyncio
async def test_batch_respects_presence_and_manual_locks(async_client, auth_headers, unique_suffix):
    obj = await _create_object(async_client, auth_headers, f"BATCH-GUARD-{unique_suffix}")
    cataloger_headers = await _create_cataloger_headers(async_client, auth_headers, unique_suffix)
    lock = await async_client.post(
        "/v1/locks",
        headers=auth_headers,
        json={"resource_type": "object", "resource_id": obj["id"], "reason": "editing"},
    )
    assert lock.status_code == 201, lock.text

    manual_lock = await async_client.post(
        "/v1/batch/object",
        headers=cataloger_headers,
        json={"ids": [obj["id"]], "operation": {"type": "set_status", "value": "internal"}},
    )
    assert manual_lock.status_code == 200, manual_lock.text
    assert manual_lock.json()["affected"] == 0
    assert "resource_locked" in manual_lock.json()["errors"][0]

    unlock = await async_client.delete(f"/v1/locks/object/{obj['id']}", headers=auth_headers)
    assert unlock.status_code == 204, unlock.text
    config = await async_client.get("/v1/admin/config", headers=auth_headers)
    assert config.status_code == 200, config.text
    previous_mode = config.json()["presence_lock_mode"]
    try:
        enable = await async_client.put(
            "/v1/admin/config", headers=auth_headers, json={"presence_lock_mode": "blocking"}
        )
        assert enable.status_code == 200, enable.text
        heartbeat = await async_client.post(
            f"/v1/presence/object/{obj['id']}/heartbeat",
            headers=auth_headers,
            json={"session_id": unique_suffix},
        )
        assert heartbeat.status_code == 200, heartbeat.text

        presence_lock = await async_client.post(
            "/v1/batch/object",
            headers=cataloger_headers,
            json={"ids": [obj["id"]], "operation": {"type": "set_status", "value": "internal"}},
        )
        assert presence_lock.status_code == 200, presence_lock.text
        assert presence_lock.json()["affected"] == 0
        assert "presence_locked" in presence_lock.json()["errors"][0]
    finally:
        release = await async_client.delete(
            f"/v1/presence/object/{obj['id']}",
            headers=auth_headers,
            params={"session_id": unique_suffix},
        )
        assert release.status_code == 204, release.text
        restore = await async_client.put(
            "/v1/admin/config", headers=auth_headers, json={"presence_lock_mode": previous_mode}
        )
        assert restore.status_code == 200, restore.text


@pytest.mark.asyncio
async def test_batch_via_filters_cross_page(async_client, auth_headers, unique_suffix):
    created = []
    for i in range(5):
        obj = await _create_object(
            async_client,
            auth_headers,
            f"BATCH-FILTER-{i}-{unique_suffix}",
            metadata={"label": f"Cross-page target {unique_suffix}"},
        )
        created.append(obj["id"])

    # Also create an object that does not match the query.
    await _create_object(
        async_client,
        auth_headers,
        f"BATCH-FILTER-OTHER-{unique_suffix}",
        metadata={"label": "Other label"},
    )

    response = await async_client.post(
        "/v1/batch/object",
        headers=auth_headers,
        json={
            "filters": {"q": f"Cross-page target {unique_suffix}"},
            "operation": {"type": "set_status", "value": "internal"},
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["affected"] == 5
    assert result["errors"] == []

    for obj_id in created:
        obj = (await async_client.get(f"/v1/objects/{obj_id}", headers=auth_headers)).json()
        assert obj["status"] == "internal"


@pytest.mark.asyncio
async def test_batch_invalid_field_returns_error(async_client, auth_headers, unique_suffix):
    obj = await _create_object(async_client, auth_headers, f"BATCH-ERR-{unique_suffix}")

    response = await async_client.post(
        "/v1/batch/object",
        headers=auth_headers,
        json={
            "ids": [obj["id"]],
            "operation": {"type": "set_field", "field": "does_not_exist", "value": "x"},
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["affected"] == 0
    assert len(result["errors"]) == 1
    assert "does_not_exist" in result["errors"][0]


@pytest.mark.asyncio
async def test_batch_requires_update_permission(async_client, auth_headers, unique_suffix):
    # A viewer user never has update permission.
    user_response = await async_client.post(
        "/v1/users",
        headers=auth_headers,
        json={
            "email": f"viewer-{unique_suffix}@katalon.dev",
            "password": "Viewer1234",
            "role": "viewer",
        },
    )
    assert user_response.status_code == 201, user_response.text

    viewer_token = (
        await async_client.post(
            "/v1/auth/token",
            data={"username": f"viewer-{unique_suffix}@katalon.dev", "password": "Viewer1234"},
        )
    ).json()["access_token"]
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    obj = await _create_object(async_client, auth_headers, f"BATCH-PERM-{unique_suffix}")

    response = await async_client.post(
        "/v1/batch/object",
        headers=viewer_headers,
        json={
            "ids": [obj["id"]],
            "operation": {"type": "set_status", "value": "public"},
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_batch_async_path_for_large_set(
    async_client, auth_headers, unique_suffix, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(batch_edit_task, "update_state", lambda **kwargs: None)

    ids = await _create_objects_bulk(101, f"BATCH-ASYNC-{unique_suffix}")

    users = (await async_client.get("/v1/users", headers=auth_headers)).json()
    admin_id = next(u["id"] for u in users if u["email"] == "admin@katalon.dev")

    payload = {
        "ids": ids,
        "operation": {"type": "set_status", "value": "public"},
    }
    response = await async_client.post(
        "/v1/batch/object",
        headers=auth_headers,
        json=payload,
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["task_id"] is not None
    assert result["batch_job_id"] is not None
    assert result["affected"] == 0
    assert result["errors"] == []

    # Execute the asynchronous batch task
    task_result = await asyncio.to_thread(
        batch_edit_task.run,
        "object",
        payload,
        admin_id,
        result["batch_job_id"],
    )
    assert task_result["affected"] == 101, task_result
    assert task_result["errors"] == []
    assert task_result["batch_job_id"] == result["batch_job_id"]

    # Invariant: All 101 records were actually modified in DB
    async with database_module.AsyncSessionLocal() as session:
        records = (
            (
                await session.execute(
                    select(Object).where(Object.id.in_([uuid.UUID(i) for i in ids]))
                )
            )
            .scalars()
            .all()
        )
        assert len(records) == 101
        assert all(r.status == "public" for r in records)

        # Invariant: Audit entry with action batch_update and matching batch_job_id for all records
        audits = (
            (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.record_type == "object",
                        AuditLog.record_id.in_([uuid.UUID(i) for i in ids]),
                        AuditLog.action == "batch_update",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(audits) == 101
        assert all(
            entry.changed_fields.get("batch_job_id") == result["batch_job_id"] for entry in audits
        )

    # Spot check via API
    spot_obj = (await async_client.get(f"/v1/objects/{ids[0]}", headers=auth_headers)).json()
    assert spot_obj["status"] == "public"
    spot_audit = (
        await async_client.get(f"/v1/objects/{ids[0]}/audit-log", headers=auth_headers)
    ).json()
    assert any(
        entry["action"] == "batch_update"
        and entry.get("changed_fields", {}).get("batch_job_id") == result["batch_job_id"]
        for entry in spot_audit
    )


@pytest.mark.asyncio
async def test_batch_async_respects_locks_and_locked_fields_above_threshold(
    async_client, auth_headers, unique_suffix, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(batch_edit_task, "update_state", lambda **kwargs: None)

    field_name = f"locked_async_{unique_suffix}"
    schema = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "object",
            "name": field_name,
            "label": {"de": "Gesperrtes Feld"},
            "field_type": "text",
            "settings": {"is_locked": True},
        },
    )
    assert schema.status_code == 201, schema.text

    ids = await _create_objects_bulk(
        101, f"BATCH-LOCK-{unique_suffix}", metadata={field_name: "Original"}
    )
    cataloger_id, cataloger_headers = await _create_cataloger_user(
        async_client, auth_headers, unique_suffix
    )

    # Active lock on first record
    lock = await async_client.post(
        "/v1/locks",
        headers=auth_headers,
        json={"resource_type": "object", "resource_id": ids[0], "reason": "editing"},
    )
    assert lock.status_code == 201, lock.text

    try:
        # Part 1: Status change by cataloger. ids[0] must be blocked by resource lock.
        payload_status = {
            "ids": ids,
            "operation": {"type": "set_status", "value": "public"},
        }
        dispatch_status = await async_client.post(
            "/v1/batch/object",
            headers=cataloger_headers,
            json=payload_status,
        )
        assert dispatch_status.status_code == 200, dispatch_status.text
        status_info = dispatch_status.json()
        assert status_info["task_id"] is not None

        task_result = await asyncio.to_thread(
            batch_edit_task.run,
            "object",
            payload_status,
            cataloger_id,
            status_info["batch_job_id"],
        )
        assert task_result["affected"] == 100
        assert len(task_result["errors"]) == 1
        assert "resource_locked" in task_result["errors"][0]
        assert ids[0] in task_result["errors"][0]

        # Invariant: Locked record untouched in DB, 100 sibling records updated
        async with database_module.AsyncSessionLocal() as session:
            locked_rec = await session.get(Object, uuid.UUID(ids[0]))
            assert locked_rec is not None
            assert locked_rec.status == "draft"

            unlocked_recs = (
                (
                    await session.execute(
                        select(Object).where(Object.id.in_([uuid.UUID(i) for i in ids[1:]]))
                    )
                )
                .scalars()
                .all()
            )
            assert len(unlocked_recs) == 100
            assert all(r.status == "public" for r in unlocked_recs)

        # Part 2: Field operation by cataloger on locked schema field across all 101 records.
        payload_field = {
            "ids": ids,
            "operation": {"type": "set_field", "field": field_name, "value": "Hacked"},
        }
        dispatch_field = await async_client.post(
            "/v1/batch/object",
            headers=cataloger_headers,
            json=payload_field,
        )
        assert dispatch_field.status_code == 200, dispatch_field.text
        field_info = dispatch_field.json()
        assert field_info["task_id"] is not None

        task_field_result = await asyncio.to_thread(
            batch_edit_task.run,
            "object",
            payload_field,
            cataloger_id,
            field_info["batch_job_id"],
        )
        # ids[0] was rejected by resource lock
        assert "resource_locked" in task_field_result["errors"][0]

        # Invariant: Locked field was NOT overwritten for unprivileged cataloger
        async with database_module.AsyncSessionLocal() as session:
            all_recs = (
                (
                    await session.execute(
                        select(Object).where(Object.id.in_([uuid.UUID(i) for i in ids]))
                    )
                )
                .scalars()
                .all()
            )
            assert len(all_recs) == 101
            assert all(r.metadata_.get(field_name) == "Original" for r in all_recs)
    finally:
        await async_client.delete(f"/v1/locks/object/{ids[0]}", headers=auth_headers)


@pytest.mark.asyncio
async def test_batch_async_rejects_invalid_relations_above_threshold(
    async_client, auth_headers, unique_suffix, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(batch_edit_task, "update_state", lambda **kwargs: None)

    ids = await _create_objects_bulk(101, f"BATCH-REL-ASYNC-{unique_suffix}")
    users = (await async_client.get("/v1/users", headers=auth_headers)).json()
    admin_id = next(u["id"] for u in users if u["email"] == "admin@katalon.dev")

    # Part 1: Missing / non-existent target ID
    missing_id = str(uuid.uuid4())
    payload_missing = {
        "ids": ids,
        "operation": {
            "type": "add_relation",
            "relation_to_type": "entity",
            "relation_to_id": missing_id,
            "relation_type": "related_to",
        },
    }
    dispatch_missing = await async_client.post(
        "/v1/batch/object",
        headers=auth_headers,
        json=payload_missing,
    )
    assert dispatch_missing.status_code == 200, dispatch_missing.text
    info_missing = dispatch_missing.json()
    assert info_missing["task_id"] is not None

    result_missing = await asyncio.to_thread(
        batch_edit_task.run,
        "object",
        payload_missing,
        admin_id,
        info_missing["batch_job_id"],
    )
    assert result_missing["affected"] == 0
    assert len(result_missing["errors"]) == 101
    assert all("existiert nicht oder ist gelöscht" in err for err in result_missing["errors"])

    # Part 2: Incompatible relation type (type pair constraint violation)
    vocabs = (await async_client.get("/v1/vocabularies", headers=auth_headers)).json()
    relation_vocab = next(v for v in vocabs if v.get("name") == "relation_types")
    restricted_term = f"restr_{unique_suffix[:8]}"
    term_res = await async_client.post(
        f"/v1/vocabularies/{relation_vocab['id']}/terms",
        headers=auth_headers,
        json={
            "vocabulary_id": relation_vocab["id"],
            "term": restricted_term,
            "label": {"de": "Restricted"},
            "applies_from": ["entity"],
            "applies_to": ["occurrence"],
        },
    )
    assert term_res.status_code == 201, term_res.text

    target_entity = await _create_entity(async_client, auth_headers, f"REL-TGT-{unique_suffix}")

    payload_restricted = {
        "ids": ids,
        "operation": {
            "type": "add_relation",
            "relation_to_type": "entity",
            "relation_to_id": target_entity["id"],
            "relation_type": restricted_term,
        },
    }
    dispatch_restricted = await async_client.post(
        "/v1/batch/object",
        headers=auth_headers,
        json=payload_restricted,
    )
    assert dispatch_restricted.status_code == 200, dispatch_restricted.text
    info_restricted = dispatch_restricted.json()
    assert info_restricted["task_id"] is not None

    result_restricted = await asyncio.to_thread(
        batch_edit_task.run,
        "object",
        payload_restricted,
        admin_id,
        info_restricted["batch_job_id"],
    )
    assert result_restricted["affected"] == 0
    assert len(result_restricted["errors"]) == 101
    assert all("nicht erlaubt" in err for err in result_restricted["errors"])

    # Invariant: No relations were created for any of the 101 objects
    async with database_module.AsyncSessionLocal() as session:
        rel_count = (
            await session.execute(
                select(func.count(Relation.id)).where(
                    Relation.from_id.in_([uuid.UUID(i) for i in ids])
                )
            )
        ).scalar_one()
        assert rel_count == 0


@pytest.mark.asyncio
async def test_batch_async_optimistic_locking_conflict_above_threshold(
    async_client, auth_headers, unique_suffix, monkeypatch: pytest.MonkeyPatch
):
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from katalon.config import settings
    from katalon.services import batch_service

    monkeypatch.setattr(batch_edit_task, "update_state", lambda **kwargs: None)

    ids = await _create_objects_bulk(101, f"BATCH-STALE-{unique_suffix}")
    stale_uuid = uuid.UUID(ids[50])

    users = (await async_client.get("/v1/users", headers=auth_headers)).json()
    admin_id = next(u["id"] for u in users if u["email"] == "admin@katalon.dev")

    payload = {
        "ids": ids,
        "operation": {"type": "set_status", "value": "public"},
    }
    response = await async_client.post(
        "/v1/batch/object",
        headers=auth_headers,
        json=payload,
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["task_id"] is not None
    assert result["batch_job_id"] is not None

    # Intercept status change on stale_uuid to perform a concurrent update that bumps the version
    orig_apply_status_change = batch_service._apply_status_change

    async def mock_apply_status_change(db, record, record_type, value, user_id, batch_job_id):
        if record.id == stale_uuid:
            temp_engine = create_async_engine(settings.database_url, poolclass=NullPool)
            temp_sm = async_sessionmaker(temp_engine, class_=AsyncSession, expire_on_commit=False)
            async with temp_sm() as s:
                concurrent_obj = await s.get(Object, stale_uuid)
                assert concurrent_obj is not None
                concurrent_obj.status = "internal"
                concurrent_obj.metadata_ = {"concurrent": "conflict"}
                await s.commit()
            await temp_engine.dispose()
        return await orig_apply_status_change(db, record, record_type, value, user_id, batch_job_id)

    monkeypatch.setattr(batch_service, "_apply_status_change", mock_apply_status_change)

    task_result = await asyncio.to_thread(
        batch_edit_task.run,
        "object",
        payload,
        admin_id,
        result["batch_job_id"],
    )

    # Invariant: Conflict reported for the stale record, 100 sibling records succeed
    assert task_result["affected"] == 100
    assert len(task_result["errors"]) == 1
    assert f"{stale_uuid}: Datensatz wurde zwischenzeitlich geändert." in task_result["errors"][0]

    # Invariant: Stale record is not silently overwritten, siblings are updated
    async with database_module.AsyncSessionLocal() as session:
        stale_record = await session.get(Object, stale_uuid)
        assert stale_record is not None
        assert stale_record.status == "internal"
        assert stale_record.metadata_ == {"concurrent": "conflict"}

        # No batch_update audit log committed for the rolled-back stale record
        stale_audits = (
            (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.record_type == "object",
                        AuditLog.record_id == stale_uuid,
                        AuditLog.action == "batch_update",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(stale_audits) == 0

        # All other 100 records were successfully updated to public
        other_records = (
            (
                await session.execute(
                    select(Object).where(
                        Object.id.in_([uuid.UUID(i) for i in ids if i != str(stale_uuid)])
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(other_records) == 100
        assert all(r.status == "public" for r in other_records)

        # All 100 successful records have the batch_update audit log
        other_audits = (
            (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.record_type == "object",
                        AuditLog.record_id.in_([uuid.UUID(i) for i in ids if i != str(stale_uuid)]),
                        AuditLog.action == "batch_update",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(other_audits) == 100
        assert all(
            a.changed_fields.get("batch_job_id") == result["batch_job_id"] for a in other_audits
        )
