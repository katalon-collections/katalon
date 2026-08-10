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
    refresh_token = payload.get("refresh_token")
    assert isinstance(token, str) and token
    assert isinstance(refresh_token, str) and refresh_token

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
    refresh_token = login.json()["refresh_token"]

    response = await async_client.post(
        "/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload.get("access_token"), str) and payload["access_token"]
    assert isinstance(payload.get("refresh_token"), str) and payload["refresh_token"]


@pytest.mark.asyncio
async def test_refresh_token_cannot_access_protected_endpoint(async_client) -> None:
    login = await async_client.post(
        "/v1/auth/token",
        data={"username": "admin@katalon.dev", "password": "admin"},
    )
    assert login.status_code == 200
    refresh_token = login.json()["refresh_token"]

    me = await async_client.get("/v1/users/me", headers={"Authorization": f"Bearer {refresh_token}"})

    assert me.status_code == 401


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
