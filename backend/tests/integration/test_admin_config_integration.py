import pytest


@pytest.mark.asyncio
async def test_admin_config_includes_ai_usage(async_client, auth_headers) -> None:
    response = await async_client.get("/v1/admin/config", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["ai_usage"] == {
        "daily_user_tokens": 0,
        "monthly_global_tokens": 0,
    }
