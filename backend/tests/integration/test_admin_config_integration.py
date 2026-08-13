import pytest


@pytest.mark.asyncio
async def test_admin_config_includes_ai_usage(async_client, auth_headers) -> None:
    response = await async_client.get("/v1/admin/config", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["ai_usage"] == {
        "daily_user_tokens": 0,
        "monthly_global_tokens": 0,
    }


@pytest.mark.asyncio
async def test_admin_config_saves_media_rights_defaults(async_client, auth_headers) -> None:
    response = await async_client.put(
        "/v1/admin/config",
        headers=auth_headers,
        json={
            "media_default_license_uri": "https://creativecommons.org/licenses/by/4.0/",
            "media_default_rights_holder": {"name": "Museum"},
        },
    )

    assert response.status_code == 200
    assert response.json()["media_default_license_uri"].endswith("/by/4.0/")
    assert response.json()["media_default_rights_holder"] == {"name": "Museum"}
