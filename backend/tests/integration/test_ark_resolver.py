# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid

import pytest


@pytest.mark.asyncio
async def test_ark_resolver_redirects_only_public_records(
    async_client, auth_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    from katalon.api.v1 import ark as ark_api

    monkeypatch.setattr(ark_api.settings, "ark_naan", "12345")
    monkeypatch.setattr(ark_api.settings, "ark_enabled", False)
    monkeypatch.setattr(ark_api.settings, "katalon_base_url", "https://catalog.example.org")

    public = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"ARK-PUBLIC-{uuid.uuid4().hex}",
            "status": "public",
            "metadata_": {"label": "Public ARK object", "pid": {"value": "ark:/12345/public", "label": "ARK"}},
        },
    )
    assert public.status_code == 201, public.text

    response = await async_client.get("/ark:/12345/public", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"https://catalog.example.org/objects/{public.json()['id']}"

    draft = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"ARK-DRAFT-{uuid.uuid4().hex}",
            "status": "draft",
            "metadata_": {"label": "Draft ARK object", "pid": {"value": "ark:/12345/draft", "label": "ARK"}},
        },
    )
    assert draft.status_code == 201, draft.text
    assert (await async_client.get("/ark:/12345/draft")).status_code == 404
    assert (await async_client.get("/ark:/99999/public")).status_code == 404

    # Soft-deleting a previously-public record keeps its ARK resolving to the
    # portal detail URL (which returns HTTP 410 Gone); soft-deleting a draft stays 404.
    del_public = await async_client.delete(f"/v1/objects/{public.json()['id']}", headers=auth_headers)
    assert del_public.status_code == 204
    gone_redirect = await async_client.get("/ark:/12345/public", follow_redirects=False)
    assert gone_redirect.status_code == 303
    assert gone_redirect.headers["location"] == f"https://catalog.example.org/objects/{public.json()['id']}"
    assert (await async_client.get(f"/portal/v1/objects/{public.json()['id']}")).status_code == 410
    assert (
        await async_client.get(f"/portal/v1/objects/{public.json()['id']}", headers=auth_headers)
    ).status_code == 410

    del_draft = await async_client.delete(f"/v1/objects/{draft.json()['id']}", headers=auth_headers)
    assert del_draft.status_code == 204
    assert (await async_client.get("/ark:/12345/draft")).status_code == 404
    assert (await async_client.get(f"/portal/v1/objects/{draft.json()['id']}")).status_code == 404
