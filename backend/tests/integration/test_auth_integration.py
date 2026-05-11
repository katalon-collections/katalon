import pytest


@pytest.mark.asyncio
async def test_login_returns_jwt_and_allows_me(async_client) -> None:
    login = await async_client.post(
        "/v1/auth/token",
        data={"username": "admin@katalon.dev", "password": "admin"},
    )

    assert login.status_code == 200
    token = login.json().get("access_token")
    assert isinstance(token, str) and token

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
