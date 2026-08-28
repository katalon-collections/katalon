import asyncio
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from katalon.core.concurrency import flush_record
from katalon.core.models import MediaFile, Object


@pytest.mark.asyncio
async def test_object_crud_roundtrip(async_client, auth_headers) -> None:
    idno = f"INT-{uuid.uuid4().hex[:12]}"

    create_response = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": idno,
            "status": "draft",
            "metadata_": {"label": "Integration object"},
        },
    )
    assert create_response.status_code == 201

    created = create_response.json()
    object_id = created["id"]
    assert created["idno"] == idno
    assert created["status"] == "draft"

    get_response = await async_client.get(f"/v1/objects/{object_id}", headers=auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["metadata_"]["label"] == "Integration object"

    update_response = await async_client.put(
        f"/v1/objects/{object_id}",
        headers=auth_headers,
        json={
            "idno": idno,
            "status": "public",
            "metadata_": {"label": "Updated integration object"},
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "public"

    delete_response = await async_client.delete(f"/v1/objects/{object_id}", headers=auth_headers)
    assert delete_response.status_code == 204

    missing_response = await async_client.get(f"/v1/objects/{object_id}", headers=auth_headers)
    assert missing_response.status_code == 404


@pytest.mark.asyncio
async def test_public_object_can_omit_subtype_when_subtypes_exist(async_client, auth_headers) -> None:
    idno = f"OPTIONAL-SUBTYPE-{uuid.uuid4().hex[:12]}"
    created = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={"idno": idno, "status": "draft", "metadata_": {"label": "Optional subtype"}},
    )
    assert created.status_code == 201, created.text

    subtype = await async_client.post(
        "/v1/record-subtypes",
        headers=auth_headers,
        json={
            "primary_type": "object",
            "name": f"optional_subtype_{uuid.uuid4().hex[:8]}",
            "label": {"de": "Optional"},
        },
    )
    assert subtype.status_code == 201, subtype.text

    updated = await async_client.put(
        f"/v1/objects/{created.json()['id']}",
        headers={**auth_headers, "If-Match": str(created.json()["version"])},
        json={"idno": idno, "status": "public", "metadata_": {"label": "Optional subtype"}},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["object_type"] is None

    deleted_subtype = await async_client.delete(
        f"/v1/record-subtypes/{subtype.json()['id']}", headers=auth_headers
    )
    assert deleted_subtype.status_code == 204, deleted_subtype.text


@pytest.mark.asyncio
async def test_object_list_search_matches_metadata_substring(async_client, auth_headers) -> None:
    suffix = uuid.uuid4().hex[:12]
    create_response = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"SEARCH-{suffix}",
            "status": "draft",
            "metadata_": {"label": f"Steinaxt-{suffix}"},
        },
    )
    assert create_response.status_code == 201, create_response.text

    response = await async_client.get(
        f"/v1/objects?q=aXt-{suffix}", headers=auth_headers
    )

    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()["items"]] == [create_response.json()["id"]]


@pytest.mark.asyncio
async def test_delete_object_with_media_files_succeeds(async_client, auth_headers) -> None:
    """Regression test: deleting an object with media files doesn't 500. Delete is a
    soft-delete now (see test_soft_delete.py) — media rows stay until the purge job
    hard-deletes the object, at which point Object.media_files' cascade/passive_deletes
    config avoids the media_files.object_id NOT NULL violation this test used to catch."""
    create_response = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={"idno": f"INT-MEDIA-{uuid.uuid4().hex[:12]}", "status": "draft", "metadata_": {}},
    )
    assert create_response.status_code == 201
    object_id = create_response.json()["id"]

    from katalon.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        session.add(
            MediaFile(
                object_id=uuid.UUID(object_id),
                filename="delete-me.jpg",
                mime_type="image/jpeg",
                file_path="/not-needed-for-this-test.jpg",
                status="ready",
            )
        )
        await session.commit()

    delete_response = await async_client.delete(f"/v1/objects/{object_id}", headers=auth_headers)
    assert delete_response.status_code == 204, delete_response.text

    missing_response = await async_client.get(f"/v1/objects/{object_id}", headers=auth_headers)
    assert missing_response.status_code == 404

    async with AsyncSessionLocal() as session:
        obj_result = await session.execute(select(Object).where(Object.id == uuid.UUID(object_id)))
        obj = obj_result.scalar_one()
        assert obj.deleted_at is not None

        media_result = await session.execute(select(MediaFile).where(MediaFile.object_id == uuid.UUID(object_id)))
        assert media_result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_object_draft_allows_missing_required_fields(async_client, auth_headers) -> None:
    field_name = f"title_required_{uuid.uuid4().hex[:8]}"
    field_response = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "object",
            "name": field_name,
            "label": {"de": "Pflichttitel"},
            "field_type": "text",
            "is_required": True,
            "is_repeatable": False,
        },
    )
    assert field_response.status_code == 201, field_response.text

    draft_response = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"OBJ-{uuid.uuid4().hex[:12]}",
            "status": "draft",
            "metadata_": {"label": "Draft object"},
        },
    )
    assert draft_response.status_code == 201, draft_response.text

    public_response = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"OBJ-{uuid.uuid4().hex[:12]}",
            "status": "public",
            "metadata_": {"label": "Public object"},
        },
    )
    assert public_response.status_code == 422
    assert field_name in str(public_response.json()["detail"])


@pytest.mark.asyncio
async def test_concurrent_object_writes_only_allow_one_winner(
    async_client, auth_headers
) -> None:
    created = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"RACE-{uuid.uuid4().hex[:12]}",
            "status": "draft",
            "metadata_": {},
        },
    )
    assert created.status_code == 201, created.text

    from katalon.database import AsyncSessionLocal

    object_id = uuid.UUID(created.json()["id"])
    async with AsyncSessionLocal() as first, AsyncSessionLocal() as second:
        first_obj = (await first.execute(select(Object).where(Object.id == object_id))).scalar_one()
        second_obj = (await second.execute(select(Object).where(Object.id == object_id))).scalar_one()
        first_obj.status = "public"
        second_obj.status = "archived"
        await first.commit()
        with pytest.raises(HTTPException) as conflict:
            await flush_record(second, second_obj)
        assert conflict.value.status_code == 409
        assert conflict.value.detail == {"error": "version_conflict", "current_version": 2}

    persisted = await async_client.get(f"/v1/objects/{object_id}", headers=auth_headers)
    assert persisted.json()["status"] == "public"
    assert persisted.json()["version"] == 2


@pytest.mark.asyncio
async def test_import_savepoint_isolates_stale_row_from_batch(
    async_client, auth_headers
) -> None:
    """Reproduces the import worker's per-row upsert pattern: a version conflict
    on one row must roll back only that row's SAVEPOINT, not poison the shared
    session so later rows in the same batch still commit."""
    from sqlalchemy.orm.exc import StaleDataError

    from katalon.database import AsyncSessionLocal

    created = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"IMPORT-{uuid.uuid4().hex[:12]}",
            "status": "draft",
            "metadata_": {},
        },
    )
    assert created.status_code == 201, created.text
    object_id = uuid.UUID(created.json()["id"])

    async with AsyncSessionLocal() as batch_session, AsyncSessionLocal() as other:
        batch_obj = (
            await batch_session.execute(select(Object).where(Object.id == object_id))
        ).scalar_one()

        # A concurrent request bumps the version behind the batch session's back.
        other_obj = (await other.execute(select(Object).where(Object.id == object_id))).scalar_one()
        other_obj.metadata_ = {"label": "concurrent edit"}
        await other.commit()

        # Row 1 of the "import batch": stale write, must not blow up the session.
        conflict = False
        try:
            async with batch_session.begin_nested():
                batch_obj.metadata_ = {"label": "import row 1"}
                await batch_session.flush()
        except StaleDataError:
            conflict = True
        assert conflict is True

        # Row 2 of the same batch: a brand-new insert must still succeed on the
        # same session/transaction after the savepoint rollback.
        second = Object(idno=f"IMPORT2-{uuid.uuid4().hex[:12]}", status="draft", metadata_={})
        batch_session.add(second)
        async with batch_session.begin_nested():
            await batch_session.flush()
        await batch_session.commit()

    persisted = await async_client.get(f"/v1/objects/{object_id}", headers=auth_headers)
    assert persisted.json()["metadata_"] == {"label": "concurrent edit"}


@pytest.mark.asyncio
async def test_snapshot_restore_requires_current_version_and_writes_audit(
    async_client, auth_headers
) -> None:
    created = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"SNAP-{uuid.uuid4().hex[:12]}",
            "status": "draft",
            "collection_status": "active",
            "metadata_": {"label": "before"},
        },
    )
    record = created.json()
    object_id = record["id"]
    snapshot = await async_client.post(
        f"/v1/objects/{object_id}/snapshots",
        headers=auth_headers,
        json={"label": "before edit"},
    )
    assert snapshot.status_code == 201, snapshot.text

    updated = await async_client.put(
        f"/v1/objects/{object_id}",
        headers={**auth_headers, "If-Match": str(record["version"])},
        json={
            "idno": record["idno"],
            "status": "draft",
            "collection_status": "pending",
            "metadata_": {"label": "after"},
        },
    )
    assert updated.status_code == 200, updated.text

    restore_url = f"/v1/objects/{object_id}/snapshots/{snapshot.json()['id']}/restore"
    missing = await async_client.post(restore_url, headers=auth_headers)
    assert missing.status_code == 428
    stale = await async_client.post(
        restore_url,
        headers={**auth_headers, "If-Match": str(record["version"])},
    )
    assert stale.status_code == 409

    restored = await async_client.post(
        restore_url,
        headers={**auth_headers, "If-Match": str(updated.json()["version"])},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["metadata_"] == {"label": "before"}
    assert restored.json()["collection_status"] == "active"
    assert restored.json()["version"] == updated.json()["version"] + 1

    audit = await async_client.get(f"/v1/objects/{object_id}/audit-log", headers=auth_headers)
    assert any(entry["action"] == "restore" for entry in audit.json())


@pytest.mark.asyncio
async def test_concurrent_duplicate_idno_returns_client_error(async_client, auth_headers) -> None:
    idno = f"DUP-{uuid.uuid4().hex[:12]}"
    payload = {
        "idno": idno,
        "status": "draft",
        "metadata_": {},
    }
    responses = await asyncio.gather(
        async_client.post("/v1/objects", headers=auth_headers, json=payload),
        async_client.post("/v1/objects", headers=auth_headers, json=payload),
    )
    assert sorted(response.status_code for response in responses) == [201, 400]
