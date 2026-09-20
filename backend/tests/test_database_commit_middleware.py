# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from katalon.api.v1.auth import hash_password
from katalon.core.dependencies import get_current_user
from katalon.core.models import User
from katalon.database import get_db
from katalon.main import app


def _mock_result(value=None):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    result.scalars.return_value.all.return_value = value or []
    return result


@pytest.fixture
def mock_admin_and_db():
    session = AsyncMock()

    def mock_add(instance):
        if hasattr(instance, "id") and instance.id is None:
            instance.id = uuid.uuid4()
        if hasattr(instance, "is_active") and instance.is_active is None:
            instance.is_active = True
        if hasattr(instance, "created_at") and instance.created_at is None:
            instance.created_at = datetime.now()

    session.add = MagicMock(side_effect=mock_add)
    session.execute = AsyncMock(return_value=_mock_result(None))
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.is_active = True
    session.in_transaction = MagicMock(return_value=True)
    session.info = {}

    admin = User(
        id=uuid.uuid4(),
        email="admin@example.org",
        hashed_password=hash_password("Current123"),
        role="admin",
        is_active=True,
        created_at=datetime.now(),
    )

    async def override_db():
        from katalon.database import register_current_session

        register_current_session(session)
        yield session

    async def override_user():
        return admin

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    yield session, admin
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_commit_before_response_on_success(mock_admin_and_db) -> None:
    """Verify that mutations are committed via DatabaseCommitMiddleware before
    the HTTP response is sent.
    """
    session, _ = mock_admin_and_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_res = await client.post(
            "/v1/users",
            json={
                "email": "immediate_test@katalon.dev",
                "password": "Password123!",
                "role": "cataloger",
            },
        )
        assert create_res.status_code == 201
        session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_no_commit_on_client_error(mock_admin_and_db) -> None:
    """Verify that on 4xx error (e.g. invalid role), no commit occurs."""
    session, _ = mock_admin_and_db
    session.commit.reset_mock()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/v1/users",
            json={
                "email": "invalid_role_test@katalon.dev",
                "password": "Password123!",
                "role": "non_existent_role",
            },
        )
        assert res.status_code == 422
        session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_commit_on_get_request(mock_admin_and_db) -> None:
    """Verify that safe HTTP methods (GET) do not commit in middleware."""
    session, _ = mock_admin_and_db
    session.commit.reset_mock()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/v1/users/me")
        assert res.status_code == 200
        session.commit.assert_not_awaited()


