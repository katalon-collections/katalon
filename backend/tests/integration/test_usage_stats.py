# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Anonymous view/download counters and the portal download/stat switches."""

import uuid

import pytest

BROWSER = {"User-Agent": "Mozilla/5.0 (Macintosh) Firefox/140.0"}


async def _object(client, headers, status: str = "public") -> str:
    created = await client.post(
        "/v1/objects",
        headers=headers,
        json={"idno": f"USE-{uuid.uuid4().hex[:10]}", "status": status, "metadata_": {"label": "x"}},
    )
    assert created.status_code == 201, created.text
    return str(created.json()["id"])


async def _media(object_id: str, media_root) -> uuid.UUID:
    import katalon.database as database_module
    from katalon.core.models import MediaFile

    path = media_root / "us" / "file.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4")
    media_id = uuid.uuid4()
    async with database_module.AsyncSessionLocal() as session:
        session.add(
            MediaFile(
                id=media_id,
                object_id=uuid.UUID(object_id),
                filename="file.pdf",
                mime_type="application/pdf",
                storage_key="us/file.pdf",
                status="ready",
                is_public=True,
            )
        )
        await session.commit()
    return media_id


async def _usage(client, headers, object_id: str) -> dict:
    response = await client.get(f"/v1/usage/object/{object_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def _portal(client, headers, **values) -> None:
    response = await client.put("/v1/portal/config", headers=headers, json=values)
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_views_count_only_anonymous_browsers_on_public_records(
    async_client, auth_headers
) -> None:
    public = await _object(async_client, auth_headers)
    draft = await _object(async_client, auth_headers, status="draft")
    view = f"/portal/v1/usage/objects/{public}/view"

    # Portal display off by default: counted, but nothing returned.
    assert (await async_client.post(view, headers=BROWSER)).status_code == 204
    await async_client.post(view)  # httpx user agent counts as a bot
    await async_client.post(view, headers={**BROWSER, **auth_headers})  # staff
    assert (
        await async_client.post(f"/portal/v1/usage/objects/{draft}/view", headers=BROWSER)
    ).status_code == 404

    usage = await _usage(async_client, auth_headers, public)
    assert usage == {"enabled": True, "views": 1, "downloads": 0, "views_30d": 1, "downloads_30d": 0}

    await _portal(async_client, auth_headers, show_usage_stats=True)
    try:
        shown = await async_client.post(view, headers=BROWSER)
        assert shown.status_code == 200
        # Downloads stay hidden while the portal offers no downloads.
        assert shown.json() == {"views": 2, "downloads": None}
        config = (await async_client.get("/portal/v1/portal/config")).json()
        assert config["show_usage_stats"] is True
        assert config["usage_stats_enabled"] is True
    finally:
        await _portal(async_client, auth_headers, show_usage_stats=False)


@pytest.mark.asyncio
async def test_global_switch_stops_counting_and_display(async_client, auth_headers) -> None:
    public = await _object(async_client, auth_headers)
    await _portal(async_client, auth_headers, show_usage_stats=True)
    off = await async_client.put(
        "/v1/admin/config", headers=auth_headers, json={"usage_stats_enabled": False}
    )
    assert off.status_code == 200 and off.json()["usage_stats_enabled"] is False
    try:
        response = await async_client.post(
            f"/portal/v1/usage/objects/{public}/view", headers=BROWSER
        )
        assert response.status_code == 204
        assert (await async_client.get("/portal/v1/portal/config")).json()[
            "usage_stats_enabled"
        ] is False
        usage = await _usage(async_client, auth_headers, public)
        assert usage["enabled"] is False and usage["views"] == 0
    finally:
        await async_client.put(
            "/v1/admin/config", headers=auth_headers, json={"usage_stats_enabled": True}
        )
        await _portal(async_client, auth_headers, show_usage_stats=False)


@pytest.mark.asyncio
async def test_download_requires_portal_switch_and_counts(
    async_client, auth_headers, monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr("katalon.config.settings.media_root", str(tmp_path / "media"))
    object_id = await _object(async_client, auth_headers)
    media_id = await _media(object_id, tmp_path / "media")
    download = f"/portal/v1/media/{media_id}/download"

    assert (await async_client.get(download, headers=BROWSER)).status_code == 404
    # Staff may still download without the switch, and is not counted.
    assert (await async_client.get(download, headers={**BROWSER, **auth_headers})).status_code == 200

    await _portal(async_client, auth_headers, media_download_enabled=True, show_usage_stats=True)
    try:
        assert (await async_client.get(download, headers=BROWSER)).status_code == 200
        resumed = await async_client.get(download, headers={**BROWSER, "Range": "bytes=4-"})
        assert resumed.status_code in (200, 206)
        await async_client.get(download)  # bot
        assert (await _usage(async_client, auth_headers, object_id))["downloads"] == 1

        shown = await async_client.post(
            f"/portal/v1/usage/objects/{object_id}/view", headers=BROWSER
        )
        assert shown.json() == {"views": 1, "downloads": 1}
    finally:
        await _portal(
            async_client, auth_headers, media_download_enabled=False, show_usage_stats=False
        )


@pytest.mark.asyncio
async def test_purge_removes_usage_rows(async_client, auth_headers) -> None:
    from sqlalchemy import func, select

    import katalon.database as database_module
    from katalon.core.models import RecordUsageDaily

    object_id = await _object(async_client, auth_headers)
    await async_client.post(f"/portal/v1/usage/objects/{object_id}/view", headers=BROWSER)
    assert (await async_client.delete(f"/v1/objects/{object_id}", headers=auth_headers)).status_code in (200, 204)
    purge = await async_client.post(f"/v1/objects/{object_id}/purge", headers=auth_headers)
    assert purge.status_code == 204, purge.text

    async with database_module.AsyncSessionLocal() as session:
        remaining = await session.scalar(
            select(func.count()).select_from(RecordUsageDaily).where(
                RecordUsageDaily.record_id == uuid.UUID(object_id)
            )
        )
    assert remaining == 0
