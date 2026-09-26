# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from katalon.api.v1.auth import hash_password
from katalon.core.dependencies import get_current_user
from katalon.core.models import User
from katalon.database import get_db
from katalon.main import app


def _user() -> User:
    return User(
        id=uuid.uuid4(), email="a@example.org", hashed_password=hash_password("Current123"),
        role="editor", is_active=True, token_version=0, created_at=datetime.now(),
    )


@pytest.mark.asyncio
async def test_logout_others_bumps_token_version_and_reissues_tokens() -> None:
    user = _user()

    async def override_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            with patch("katalon.api.v1.auth.get_user_features", AsyncMock(return_value=[])):
                response = await client.post("/v1/auth/logout-others")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert "katalon_refresh_token" in response.headers["set-cookie"]
    assert user.token_version == 1


@pytest.mark.asyncio
async def test_login_unknown_email_still_verifies_a_hash() -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session = AsyncMock()
    session.execute.return_value = result

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        with patch("katalon.api.v1.auth.verify_password", return_value=False) as verify:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post(
                    "/v1/auth/token", data={"username": "nobody@example.org", "password": "x"}
                )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    verify.assert_called_once()
