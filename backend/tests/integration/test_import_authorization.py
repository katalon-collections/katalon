# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Issue #389: import (dry-run, the queued run, and the async Celery path) must
require the `import` feature *and* record-write permission (create+update) for
the record type being imported — replacing the previous coarse `manage_content`
gate, and re-checking status/feature/record permission at execution time.
"""

import asyncio
import uuid
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import select

import katalon.database as database_module
from katalon.core.models import Object


class _FakeRedis:
    """Stand-in for redis.from_url — the import task's cancel-check only calls .get()."""

    def get(self, key: str) -> None:
        return None


def _patch_no_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    from katalon.workers.import_tasks import import_records_task

    monkeypatch.setattr("redis.from_url", lambda *args, **kwargs: _FakeRedis())
    monkeypatch.setattr(import_records_task, "update_state", lambda **kwargs: None)


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
async def _record_permissions_revoked(
    async_client, auth_headers, role: str, record_type: str, actions: list[str]
):
    """Temporarily drop the given (record_type, action) grants from `role`,
    restoring the role's exact prior set afterward (see `_feature_revoked`)."""
    current = (await async_client.get("/v1/users/permissions", headers=auth_headers)).json()
    role_rows = [row for row in current if row["role"] == role]
    remaining = [
        row
        for row in role_rows
        if not (row["record_type"] == record_type and row["action"] in actions)
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
async def test_import_dry_run_and_run_require_import_feature(async_client, auth_headers) -> None:
    _, cataloger_headers = await _create_role_user(async_client, auth_headers, "cataloger")

    async with _feature_revoked(async_client, auth_headers, "cataloger", "import"):
        body = {"record_type": "object", "upload_id": "does-not-exist", "mapping": {}}
        dry_run_res = await async_client.post(
            "/v1/importer/dry-run", headers=cataloger_headers, json=body
        )
        assert dry_run_res.status_code == 403

        run_res = await async_client.post(
            "/v1/importer/import", headers=cataloger_headers, json=body
        )
        assert run_res.status_code == 403


@pytest.mark.asyncio
async def test_import_requires_write_permission_for_chosen_record_type(
    async_client, auth_headers
) -> None:
    # Cataloger keeps the `import` feature but loses create+update on
    # `object` — the import must be denied before ever touching the upload.
    _, cataloger_headers = await _create_role_user(async_client, auth_headers, "cataloger")

    async with _record_permissions_revoked(
        async_client, auth_headers, "cataloger", "object", ["create", "update"]
    ):
        body = {"record_type": "object", "upload_id": "does-not-exist", "mapping": {}}
        dry_run_res = await async_client.post(
            "/v1/importer/dry-run", headers=cataloger_headers, json=body
        )
        assert dry_run_res.status_code == 403

        run_res = await async_client.post(
            "/v1/importer/import", headers=cataloger_headers, json=body
        )
        assert run_res.status_code == 403


@pytest.mark.asyncio
async def test_import_dry_run_proceeds_past_permission_check_when_authorized(
    async_client, auth_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Cataloger retains the default import feature + object write permission
    # — the request must clear the permission gate and fail later, on the
    # (nonexistent) upload id instead. No real Redis in this test harness,
    # so stand in for it exactly like test_import_resilience.py does.
    _patch_no_broker(monkeypatch)
    _, cataloger_headers = await _create_role_user(async_client, auth_headers, "cataloger")

    body = {"record_type": "object", "upload_id": "does-not-exist", "mapping": {}}
    dry_run_res = await async_client.post(
        "/v1/importer/dry-run", headers=cataloger_headers, json=body
    )
    assert dry_run_res.status_code == 404, dry_run_res.text


@pytest.mark.asyncio
async def test_async_import_skips_processing_when_feature_revoked_before_execution(
    async_client, auth_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    from katalon.workers.import_tasks import import_records_task

    _patch_no_broker(monkeypatch)

    idno = f"IMPORT-ASYNC-FEAT-{uuid.uuid4().hex[:10]}"
    cataloger_id, _ = await _create_role_user(async_client, auth_headers, "cataloger")
    rows = [{"idno": idno, "title": f"Title {idno}"}]
    mapping = {"idno": "__idno__", "title": "label"}

    # Enqueue would have been authorized at this point (cataloger has the
    # default `import` feature) — now revoke it, simulating a role/permission
    # change that lands between enqueue and the worker actually running.
    async with _feature_revoked(async_client, auth_headers, "cataloger", "import"):
        result = await asyncio.to_thread(
            import_records_task.run,
            "object",
            rows,
            mapping,
            idno_strategy="column",
            user_id=cataloger_id,
        )

    assert result["created"] == 0
    assert result["updated"] == 0
    assert result["errors"] == [
        {"row": None, "error": "Import-Job abgebrochen: Import-Feature wurde entzogen."}
    ]

    async with database_module.AsyncSessionLocal() as session:
        persisted = (
            await session.execute(select(Object).where(Object.idno == idno))
        ).scalar_one_or_none()
        assert persisted is None


@pytest.mark.asyncio
async def test_async_import_skips_processing_when_record_permission_revoked_before_execution(
    async_client, auth_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    from katalon.workers.import_tasks import import_records_task

    _patch_no_broker(monkeypatch)

    idno = f"IMPORT-ASYNC-PERM-{uuid.uuid4().hex[:10]}"
    cataloger_id, _ = await _create_role_user(async_client, auth_headers, "cataloger")
    rows = [{"idno": idno, "title": f"Title {idno}"}]
    mapping = {"idno": "__idno__", "title": "label"}

    async with _record_permissions_revoked(
        async_client, auth_headers, "cataloger", "object", ["create"]
    ):
        result = await asyncio.to_thread(
            import_records_task.run,
            "object",
            rows,
            mapping,
            idno_strategy="column",
            user_id=cataloger_id,
        )

    assert result["created"] == 0
    assert result["updated"] == 0
    assert result["errors"] == [
        {
            "row": None,
            "error": "Import-Job abgebrochen: Schreibrecht für diesen Datensatztyp wurde entzogen.",
        }
    ]

    async with database_module.AsyncSessionLocal() as session:
        persisted = (
            await session.execute(select(Object).where(Object.idno == idno))
        ).scalar_one_or_none()
        assert persisted is None


@pytest.mark.asyncio
async def test_async_import_skips_processing_when_user_deactivated_before_execution(
    async_client, auth_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    from katalon.workers.import_tasks import import_records_task

    _patch_no_broker(monkeypatch)

    idno = f"IMPORT-ASYNC-DEACT-{uuid.uuid4().hex[:10]}"
    cataloger_id, _ = await _create_role_user(async_client, auth_headers, "cataloger")
    rows = [{"idno": idno, "title": f"Title {idno}"}]
    mapping = {"idno": "__idno__", "title": "label"}

    deactivate_res = await async_client.put(
        f"/v1/users/{cataloger_id}",
        headers=auth_headers,
        json={"is_active": False},
    )
    assert deactivate_res.status_code == 200, deactivate_res.text

    result = await asyncio.to_thread(
        import_records_task.run,
        "object",
        rows,
        mapping,
        idno_strategy="column",
        user_id=cataloger_id,
    )

    assert result["created"] == 0
    assert result["updated"] == 0
    assert result["errors"] == [
        {
            "row": None,
            "error": "Import-Job abgebrochen: Benutzer nicht gefunden oder deaktiviert.",
        }
    ]

    async with database_module.AsyncSessionLocal() as session:
        persisted = (
            await session.execute(select(Object).where(Object.idno == idno))
        ).scalar_one_or_none()
        assert persisted is None


@pytest.mark.asyncio
async def test_async_import_succeeds_when_permission_still_intact_at_execution(
    async_client, auth_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression guard: the execution-time re-check must not break the
    ordinary case where permissions remain intact between enqueue and execution.
    """
    from katalon.workers.import_tasks import import_records_task

    _patch_no_broker(monkeypatch)

    idno = f"IMPORT-ASYNC-OK-{uuid.uuid4().hex[:10]}"
    cataloger_id, _ = await _create_role_user(async_client, auth_headers, "cataloger")
    rows = [{"idno": idno, "title": f"Title {idno}"}]
    mapping = {"idno": "__idno__", "title": "label"}

    result = await asyncio.to_thread(
        import_records_task.run,
        "object",
        rows,
        mapping,
        idno_strategy="column",
        user_id=cataloger_id,
    )

    assert result["created"] == 1, result
    assert result["updated"] == 0
    assert result["errors"] == []

    async with database_module.AsyncSessionLocal() as session:
        persisted = (
            await session.execute(select(Object).where(Object.idno == idno))
        ).scalar_one_or_none()
        assert persisted is not None
        assert persisted.metadata_["label"] == f"Title {idno}"
