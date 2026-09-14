# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import pytest

from katalon.core.limiter import limiter


@pytest.mark.asyncio
async def test_login_returns_jwt_and_allows_me(async_client) -> None:
    login = await async_client.post(
        "/v1/auth/token",
        data={"username": "admin@katalon.dev", "password": "admin"},
    )

    assert login.status_code == 200
    payload = login.json()
    token = payload.get("access_token")
    assert isinstance(token, str) and token
    assert "refresh_token" not in payload
    set_cookie = login.headers["set-cookie"]
    assert "katalon_refresh_token" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=strict" in set_cookie

    me = await async_client.get("/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "admin@katalon.dev"


@pytest.mark.asyncio
async def test_login_rejects_invalid_password(async_client) -> None:
    response = await async_client.post(
        "/v1/auth/token",
        data={"username": "admin@katalon.dev", "password": "wrong-password"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_returns_new_token_pair(async_client) -> None:
    login = await async_client.post(
        "/v1/auth/token",
        data={"username": "admin@katalon.dev", "password": "admin"},
    )
    assert login.status_code == 200
    response = await async_client.post("/v1/auth/refresh")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload.get("access_token"), str) and payload["access_token"]
    assert "refresh_token" not in payload
    assert "katalon_refresh_token" in response.headers["set-cookie"]


@pytest.mark.asyncio
async def test_refresh_token_cannot_access_protected_endpoint(async_client) -> None:
    login = await async_client.post(
        "/v1/auth/token",
        data={"username": "admin@katalon.dev", "password": "admin"},
    )
    assert login.status_code == 200
    refresh_token = async_client.cookies["katalon_refresh_token"]

    me = await async_client.get("/v1/users/me", headers={"Authorization": f"Bearer {refresh_token}"})

    assert me.status_code == 401


@pytest.mark.asyncio
async def test_logout_clears_refresh_cookie(async_client) -> None:
    login = await async_client.post(
        "/v1/auth/token",
        data={"username": "admin@katalon.dev", "password": "admin"},
    )
    assert login.status_code == 200

    response = await async_client.post("/v1/auth/logout")

    assert response.status_code == 204
    assert "katalon_refresh_token=\"\"" in response.headers["set-cookie"]

    refresh = await async_client.post("/v1/auth/refresh")
    assert refresh.status_code == 401


@pytest.mark.asyncio
async def test_login_rate_limited_after_threshold(async_client) -> None:
    limiter.reset()

    for _ in range(10):
        response = await async_client.post(
            "/v1/auth/token",
            data={"username": "admin@katalon.dev", "password": "wrong-password"},
        )
        assert response.status_code == 401

    response = await async_client.post(
        "/v1/auth/token",
        data={"username": "admin@katalon.dev", "password": "wrong-password"},
    )
    assert response.status_code == 429
