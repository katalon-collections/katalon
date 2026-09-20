# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from katalon.core.dependencies import get_current_user, get_db, try_get_current_user
from katalon.core.models import Collection, User
from katalon.main import app


def _admin_user() -> User:
    return User(id=uuid.uuid4(), email="admin@example.com", role="admin", is_active=True)


async def _get_collection(col: Collection, has_public_member: bool) -> dict:
    session = AsyncMock()
    res_col = MagicMock()
    res_col.scalar_one_or_none.return_value = col
    res_public_member = MagicMock()
    res_public_member.scalar.return_value = has_public_member
    session.execute.side_effect = [res_col, res_public_member]

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = _admin_user
    app.dependency_overrides[try_get_current_user] = lambda: _admin_user()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/v1/collections/{col.id}")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(try_get_current_user, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
async def test_public_collection_without_public_members_flags_warning() -> None:
    now = datetime.now(UTC)
    col = Collection(
        id=uuid.uuid4(),
        idno="COLL-010",
        status="public",
        metadata_={"title": "Leere Sammlung"},
        created_at=now,
        updated_at=now,
        version=1,
        ai_provenance={},
    )
    data = await _get_collection(col, has_public_member=False)
    assert data["public_without_public_members"] is True


@pytest.mark.asyncio
async def test_public_collection_with_public_member_has_no_warning() -> None:
    now = datetime.now(UTC)
    col = Collection(
        id=uuid.uuid4(),
        idno="COLL-011",
        status="public",
        metadata_={"title": "Gefüllte Sammlung"},
        created_at=now,
        updated_at=now,
        version=1,
        ai_provenance={},
    )
    data = await _get_collection(col, has_public_member=True)
    assert data["public_without_public_members"] is False


@pytest.mark.asyncio
async def test_draft_collection_never_flags_warning() -> None:
    now = datetime.now(UTC)
    col = Collection(
        id=uuid.uuid4(),
        idno="COLL-012",
        status="draft",
        metadata_={"title": "Entwurf"},
        created_at=now,
        updated_at=now,
        version=1,
        ai_provenance={},
    )
    session = AsyncMock()
    res_col = MagicMock()
    res_col.scalar_one_or_none.return_value = col
    session.execute.side_effect = [res_col]

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = _admin_user
    app.dependency_overrides[try_get_current_user] = lambda: _admin_user()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/v1/collections/{col.id}")
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(try_get_current_user, None)
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    assert response.json()["public_without_public_members"] is False
