# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from katalon.core.dependencies import get_current_user
from katalon.core.models import User, WorkingSet, WorkingSetItem
from katalon.core.schemas import (
    WorkingSetCreate,
    WorkingSetItemCreate,
    WorkingSetUpdate,
)
from katalon.database import get_db
from katalon.main import app
from katalon.services import working_set_service

# ---------------------------------------------------------------------------
# Schema Tests
# ---------------------------------------------------------------------------


def test_working_set_create_schema() -> None:
    ws = WorkingSetCreate(
        name="Meine Auswahl",
        description="Notizen",
        record_type="object",
        is_shared=False,
    )
    assert ws.name == "Meine Auswahl"
    assert ws.record_type == "object"
    assert ws.is_shared is False


def test_working_set_update_schema() -> None:
    u = WorkingSetUpdate(name="Neuer Name", is_shared=True)
    assert u.name == "Neuer Name"
    assert u.is_shared is True
    assert u.description is None


def test_working_set_item_create_schema() -> None:
    rid = uuid.uuid4()
    item = WorkingSetItemCreate(record_id=rid, sort_order=2, note="Vitrine 1")
    assert item.record_id == rid
    assert item.sort_order == 2
    assert item.note == "Vitrine 1"


# ---------------------------------------------------------------------------
# Service Unit Tests (Access & Validation)
# ---------------------------------------------------------------------------


def test_check_set_access_owner_allowed() -> None:
    user_id = uuid.uuid4()
    user = User(id=user_id, email="owner@example.org", role="editor", hashed_password="x")
    ws = WorkingSet(id=uuid.uuid4(), user_id=user_id, is_shared=False)

    # Should not raise
    working_set_service._check_set_access(ws, user, require_owner=False)
    working_set_service._check_set_access(ws, user, require_owner=True)


def test_check_set_access_admin_allowed_even_if_not_owner() -> None:
    admin = User(id=uuid.uuid4(), email="admin@example.org", role="admin", hashed_password="x")
    ws = WorkingSet(id=uuid.uuid4(), user_id=uuid.uuid4(), is_shared=False)

    working_set_service._check_set_access(ws, admin, require_owner=False)
    working_set_service._check_set_access(ws, admin, require_owner=True)


def test_check_set_access_non_owner_private_forbidden() -> None:
    user = User(id=uuid.uuid4(), email="user@example.org", role="editor", hashed_password="x")
    ws = WorkingSet(id=uuid.uuid4(), user_id=uuid.uuid4(), is_shared=False)

    with pytest.raises(HTTPException) as exc:
        working_set_service._check_set_access(ws, user, require_owner=False)
    assert exc.value.status_code == 403


def test_check_set_access_non_owner_shared_read_ok_but_not_edit() -> None:
    user = User(id=uuid.uuid4(), email="user@example.org", role="editor", hashed_password="x")
    ws = WorkingSet(id=uuid.uuid4(), user_id=uuid.uuid4(), is_shared=True)

    # Read/item access allowed
    working_set_service._check_set_access(ws, user, require_owner=False)

    # Editing set properties requires owner
    with pytest.raises(HTTPException) as exc:
        working_set_service._check_set_access(ws, user, require_owner=True)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_create_working_set_invalid_type_raises_400() -> None:
    db = AsyncMock()
    user = User(id=uuid.uuid4(), email="user@example.org", role="editor", hashed_password="x")
    data = WorkingSetCreate(name="Ungültig", record_type="invalid_type")

    with pytest.raises(HTTPException) as exc:
        await working_set_service.create_working_set(db, data, user)
    assert exc.value.status_code == 400
    assert "Ungültiger Datensatztyp" in exc.value.detail


@pytest.mark.asyncio
async def test_reorder_working_set_items() -> None:
    set_id = uuid.uuid4()
    user_id = uuid.uuid4()
    user = User(id=user_id, email="owner@example.org", role="editor", hashed_password="x")
    ws = WorkingSet(id=set_id, user_id=user_id, is_shared=False)

    item1 = WorkingSetItem(id=uuid.uuid4(), set_id=set_id, record_id=uuid.uuid4(), sort_order=0)
    item2 = WorkingSetItem(id=uuid.uuid4(), set_id=set_id, record_id=uuid.uuid4(), sort_order=1)

    db = AsyncMock()
    db.get = AsyncMock(return_value=ws)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [item1, item2]
    db.execute = AsyncMock(return_value=mock_result)

    # Reorder item2 first, then item1
    await working_set_service.reorder_working_set_items(db, set_id, [item2.id, item1.id], user)

    assert item2.sort_order == 0
    assert item1.sort_order == 1
    db.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# API Integration Tests
# ---------------------------------------------------------------------------


@pytest.fixture
def override_deps():
    session = AsyncMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()

    user = User(
        id=uuid.uuid4(),
        email="curator@example.org",
        role="editor",
        is_active=True,
        hashed_password="hash",
        created_at=datetime.now(),
    )

    async def override_db():
        yield session

    async def override_user():
        return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    yield session, user
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_list_working_sets_endpoint(override_deps) -> None:
    session, user = override_deps
    ws_id = uuid.uuid4()
    ws = WorkingSet(
        id=ws_id,
        name="Grafik-Auswahl",
        description="Für Saal 2",
        record_type="object",
        user_id=user.id,
        is_shared=False,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    mock_result = MagicMock()
    mock_result.all.return_value = [(ws, user.email, 5)]
    session.execute = AsyncMock(return_value=mock_result)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/v1/working-sets")

    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["id"] == str(ws_id)
    assert data[0]["name"] == "Grafik-Auswahl"
    assert data[0]["item_count"] == 5


@pytest.mark.asyncio
async def test_create_working_set_endpoint(override_deps) -> None:
    session, user = override_deps

    async def fake_refresh(instance):
        instance.id = uuid.uuid4()
        instance.created_at = datetime.now()
        instance.updated_at = datetime.now()

    session.refresh = AsyncMock(side_effect=fake_refresh)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/v1/working-sets",
            json={
                "name": "Neue Arbeitsliste",
                "record_type": "entity",
                "is_shared": True,
            },
        )

    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Neue Arbeitsliste"
    assert data["record_type"] == "entity"
    assert data["is_shared"] is True
    assert data["user_name"] == user.email


@pytest.mark.asyncio
async def test_delete_working_set_endpoint(override_deps) -> None:
    session, user = override_deps
    ws_id = uuid.uuid4()
    ws = WorkingSet(id=ws_id, name="Zu löschen", record_type="object", user_id=user.id, is_shared=False)
    session.get = AsyncMock(return_value=ws)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.delete(f"/v1/working-sets/{ws_id}")

    assert res.status_code == 204
    session.delete.assert_awaited_once_with(ws)


@pytest.mark.asyncio
async def test_list_working_sets_filtered_by_record_id(override_deps) -> None:
    session, user = override_deps
    target_record_id = uuid.uuid4()
    ws = WorkingSet(
        id=uuid.uuid4(),
        name="Ausstellung A",
        record_type="object",
        user_id=user.id,
        is_shared=False,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    mock_result = MagicMock()
    mock_result.all.return_value = [(ws, user.email, 1)]
    session.execute = AsyncMock(return_value=mock_result)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get(f"/v1/working-sets?record_id={target_record_id}")

    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["name"] == "Ausstellung A"
