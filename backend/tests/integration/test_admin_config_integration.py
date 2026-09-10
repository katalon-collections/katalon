# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid

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
async def test_admin_changelog_is_restricted_to_admins(async_client, auth_headers) -> None:
    unauthenticated = await async_client.get("/v1/admin/config/changelog")
    email = f"changelog-editor-{uuid.uuid4().hex}@example.com"
    created = await async_client.post(
        "/v1/users",
        headers=auth_headers,
        json={"email": email, "password": "Editor1234", "role": "editor"},
    )
    assert created.status_code == 201, created.text
    login = await async_client.post(
        "/v1/auth/token",
        data={"username": email, "password": "Editor1234"},
    )
    assert login.status_code == 200, login.text
    editor = await async_client.get(
        "/v1/admin/config/changelog",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    response = await async_client.get("/v1/admin/config/changelog", headers=auth_headers)

    assert unauthenticated.status_code == 401
    assert editor.status_code == 403
    assert response.status_code == 200
    assert response.json()["content"].startswith("# Changelog")


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


@pytest.mark.asyncio
async def test_admin_config_supported_languages_defaults_to_de_en(async_client, auth_headers) -> None:
    response = await async_client.get("/v1/admin/config", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["supported_languages"] == ["de", "en"]


@pytest.mark.asyncio
async def test_admin_config_saves_supported_languages(async_client, auth_headers) -> None:
    response = await async_client.put(
        "/v1/admin/config",
        headers=auth_headers,
        json={"supported_languages": ["de", "fr", "it"]},
    )

    assert response.status_code == 200
    assert response.json()["supported_languages"] == ["de", "fr", "it"]

