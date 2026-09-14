# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Issue #389: batch operations must require the `batch` feature, and the
async Celery path must re-check the acting user's status/feature/record
permission at execution time — not just at enqueue time — so a role change,
deactivation, or permission revocation between enqueue and execution blocks
further processing instead of silently going through on a looser check.
"""

import asyncio
import uuid
from contextlib import asynccontextmanager

import pytest


async def _create_object(async_client, auth_headers, idno: str) -> dict:
    response = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={"idno": idno, "status": "draft", "metadata_": {}},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _create_role_user(
    async_client, auth_headers: dict[str, str], role: str
) -> tuple[str, dict[str, str]]:
    email = f"{role}-{uuid.uuid4().hex[:10]}@katalon.dev"
    password = "Test1234"
    created = await async_client.post(
        "/v1/users",
        headers=auth_headers,
        json={"email": email, "password": password, "role": role},
    )
    assert created.status_code == 201, created.text
    user_id = created.json()["id"]
    token = (
        await async_client.post(
            "/v1/auth/token",
            data={"username": email, "password": password},
        )
    ).json()["access_token"]
    return user_id, {"Authorization": f"Bearer {token}"}


@asynccontextmanager
async def _feature_revoked(async_client, auth_headers, role: str, feature: str):
    """Temporarily drop `feature` from `role`'s feature permissions, restoring
    the role's exact prior set afterward — role permissions are global state
    shared by every user of that role across the whole test session."""
    current = (await async_client.get("/v1/users/features", headers=auth_headers)).json()
    role_rows = [row for row in current if row["role"] == role]
    remaining = [row for row in role_rows if row["feature"] != feature]
    res = await async_client.put(
        f"/v1/users/features/{role}",
        headers=auth_headers,
        json={"features": remaining},
    )
    assert res.status_code == 200, res.text
    try:
        yield
    finally:
        restore = await async_client.put(
            f"/v1/users/features/{role}",
            headers=auth_headers,
            json={"features": role_rows},
        )
        assert restore.status_code == 200, restore.text


@asynccontextmanager
async def _record_permission_revoked(
    async_client, auth_headers, role: str, record_type: str, action: str
):
    """Temporarily drop one (record_type, action) grant from `role`, restoring
    the role's exact prior set afterward (see `_feature_revoked`)."""
    current = (await async_client.get("/v1/users/permissions", headers=auth_headers)).json()
    role_rows = [row for row in current if row["role"] == role]
    remaining = [
        row
        for row in role_rows
        if not (row["record_type"] == record_type and row["action"] == action)
    ]
    res = await async_client.put(
        f"/v1/users/permissions/{role}",
        headers=auth_headers,
        json={"permissions": remaining},
    )
    assert res.status_code == 200, res.text
    try:
        yield
    finally:
        restore = await async_client.put(
            f"/v1/users/permissions/{role}",
            headers=auth_headers,
            json={"permissions": role_rows},
        )
        assert restore.status_code == 200, restore.text


@pytest.mark.asyncio
async def test_sync_batch_requires_batch_feature(async_client, auth_headers) -> None:
    obj = await _create_object(async_client, auth_headers, f"BATCH-FEAT-{uuid.uuid4().hex[:10]}")
    _, cataloger_headers = await _create_role_user(async_client, auth_headers, "cataloger")

    async with _feature_revoked(async_client, auth_headers, "cataloger", "batch"):
        res = await async_client.post(
            "/v1/batch/object",
            headers=cataloger_headers,
            json={"ids": [obj["id"]], "operation": {"type": "set_status", "value": "public"}},
        )
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_async_batch_skips_processing_when_feature_revoked_before_execution(
    async_client, auth_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    from katalon.workers.batch_tasks import batch_edit_task

    monkeypatch.setattr(batch_edit_task, "update_state", lambda **kwargs: None)

    idno = f"BATCH-ASYNC-FEAT-{uuid.uuid4().hex[:10]}"
    obj = await _create_object(async_client, auth_headers, idno)
    cataloger_id, _ = await _create_role_user(async_client, auth_headers, "cataloger")

    request_dict = {
        "ids": [obj["id"]],
        "operation": {"type": "set_status", "value": "public"},
    }

    # Enqueue would have been authorized at this point (cataloger has the
    # default `batch` feature) — now revoke it, simulating a role/permission
    # change that lands between enqueue and the worker actually running.
    async with _feature_revoked(async_client, auth_headers, "cataloger", "batch"):
        result = await asyncio.to_thread(
            batch_edit_task.run,
            "object",
            request_dict,
            cataloger_id,
            str(uuid.uuid4()),
        )

    assert result["affected"] == 0
    assert result["errors"], result
    assert "abgebrochen" in result["errors"][0]

    unchanged = await async_client.get(f"/v1/objects/{obj['id']}", headers=auth_headers)
    assert unchanged.json()["status"] == "draft"


@pytest.mark.asyncio
async def test_async_batch_skips_processing_when_record_permission_revoked_before_execution(
    async_client, auth_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    from katalon.workers.batch_tasks import batch_edit_task

    monkeypatch.setattr(batch_edit_task, "update_state", lambda **kwargs: None)

    idno = f"BATCH-ASYNC-PERM-{uuid.uuid4().hex[:10]}"
    obj = await _create_object(async_client, auth_headers, idno)
    cataloger_id, _ = await _create_role_user(async_client, auth_headers, "cataloger")

    request_dict = {
        "ids": [obj["id"]],
        "operation": {"type": "set_status", "value": "public"},
    }

    async with _record_permission_revoked(
        async_client, auth_headers, "cataloger", "object", "update"
    ):
        result = await asyncio.to_thread(
            batch_edit_task.run,
            "object",
            request_dict,
            cataloger_id,
            str(uuid.uuid4()),
        )

    assert result["affected"] == 0
    assert result["errors"], result

    unchanged = await async_client.get(f"/v1/objects/{obj['id']}", headers=auth_headers)
    assert unchanged.json()["status"] == "draft"


@pytest.mark.asyncio
async def test_async_batch_skips_processing_when_user_deactivated_before_execution(
    async_client, auth_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    from katalon.workers.batch_tasks import batch_edit_task

    monkeypatch.setattr(batch_edit_task, "update_state", lambda **kwargs: None)

    idno = f"BATCH-ASYNC-DEACT-{uuid.uuid4().hex[:10]}"
    obj = await _create_object(async_client, auth_headers, idno)
    cataloger_id, _ = await _create_role_user(async_client, auth_headers, "cataloger")

    deactivate_res = await async_client.put(
        f"/v1/users/{cataloger_id}",
        headers=auth_headers,
        json={"is_active": False},
    )
    assert deactivate_res.status_code == 200, deactivate_res.text

    request_dict = {
        "ids": [obj["id"]],
        "operation": {"type": "set_status", "value": "public"},
    }
    result = await asyncio.to_thread(
        batch_edit_task.run,
        "object",
        request_dict,
        cataloger_id,
        str(uuid.uuid4()),
    )

    assert result["affected"] == 0
    assert result["errors"], result
    assert "deaktiviert" in result["errors"][0]

    unchanged = await async_client.get(f"/v1/objects/{obj['id']}", headers=auth_headers)
    assert unchanged.json()["status"] == "draft"


@pytest.mark.asyncio
async def test_async_batch_still_processes_for_authorized_user(
    async_client, auth_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression guard: the new execution-time re-check must not break the
    ordinary case where nothing changed between enqueue and execution."""
    from katalon.workers.batch_tasks import batch_edit_task

    monkeypatch.setattr(batch_edit_task, "update_state", lambda **kwargs: None)

    idno = f"BATCH-ASYNC-OK-{uuid.uuid4().hex[:10]}"
    obj = await _create_object(async_client, auth_headers, idno)
    cataloger_id, _ = await _create_role_user(async_client, auth_headers, "cataloger")

    request_dict = {
        "ids": [obj["id"]],
        "operation": {"type": "set_status", "value": "public"},
    }
    result = await asyncio.to_thread(
        batch_edit_task.run,
        "object",
        request_dict,
        cataloger_id,
        str(uuid.uuid4()),
    )

    assert result["affected"] == 1, result
    assert result["errors"] == []

    updated = await async_client.get(f"/v1/objects/{obj['id']}", headers=auth_headers)
    assert updated.json()["status"] == "public"


@pytest.mark.asyncio
async def test_async_batch_respects_manual_locks(
    async_client, auth_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    from katalon.workers.batch_tasks import batch_edit_task

    monkeypatch.setattr(batch_edit_task, "update_state", lambda **kwargs: None)
    obj = await _create_object(
        async_client, auth_headers, f"BATCH-ASYNC-LOCK-{uuid.uuid4().hex[:10]}"
    )
    cataloger_id, _ = await _create_role_user(async_client, auth_headers, "cataloger")
    lock = await async_client.post(
        "/v1/locks",
        headers=auth_headers,
        json={"resource_type": "object", "resource_id": obj["id"], "reason": "editing"},
    )
    assert lock.status_code == 201, lock.text

    result = await asyncio.to_thread(
        batch_edit_task.run,
        "object",
        {"ids": [obj["id"]], "operation": {"type": "set_status", "value": "public"}},
        cataloger_id,
        str(uuid.uuid4()),
    )

    assert result["affected"] == 0
    assert "resource_locked" in result["errors"][0]
    unchanged = await async_client.get(f"/v1/objects/{obj['id']}", headers=auth_headers)
    assert unchanged.json()["status"] == "draft"
