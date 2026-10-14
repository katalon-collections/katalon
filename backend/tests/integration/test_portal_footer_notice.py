# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Configurable footer, usage notice, header options and footer images."""

import pytest

FOOTER = {
    "columns": [
        {"type": "text", "title": {"de": "Hinweis"}, "content": {"de": "Text nach **§ 86 StGB**"}},
        {
            "type": "links",
            "title": {"de": "Projekt"},
            "links": [{"label": {"de": "Uni"}, "url": "https://uni-osnabrueck.de"}],
            "include_footer_pages": True,
        },
        {
            "type": "logos",
            "logos": [{"src": "/themes/bpk/dfg.png", "alt": {"de": "DFG"}, "href": "https://dfg.de"}],
        },
    ],
    "bottom": {"text": {"de": "© Uni Osnabrück"}, "links": [{"label": {"de": "Impressum"}, "url": "/page/impressum"}]},
}


@pytest.mark.asyncio
async def test_footer_notice_and_header_options_roundtrip(async_client, auth_headers) -> None:
    response = await async_client.put(
        "/v1/portal/config",
        headers=auth_headers,
        json={
            "footer": FOOTER,
            "notice": {"enabled": True, "version": 2, "title": {"de": "Hinweis"}, "text": {"de": "Bitte beachten"}, "accept_label": {"de": "Verstanden"}},
            "header_show_title": False,
            "hero_hide_title": True,
        },
    )
    assert response.status_code == 200, response.text
    public = (await async_client.get("/portal/v1/portal/config")).json()
    assert public["footer"]["columns"][1]["include_footer_pages"] is True
    assert public["footer"]["columns"][2]["logos"][0]["src"] == "/themes/bpk/dfg.png"
    assert public["notice"]["version"] == 2 and public["notice"]["enabled"] is True
    assert public["header_show_title"] is False and public["hero_hide_title"] is True


@pytest.mark.asyncio
async def test_defaults_keep_the_one_line_footer(async_client, auth_headers) -> None:
    await async_client.put("/v1/portal/config", headers=auth_headers, json={"footer": {}, "notice": {}})
    public = (await async_client.get("/portal/v1/portal/config")).json()
    assert public["footer"] == {"columns": [], "bottom": {"text": {}, "links": []}}
    assert public["notice"]["enabled"] is False


@pytest.mark.parametrize(
    "bad_url", ["javascript:alert(1)", "data:text/html,x", "//evil.example/x", "ftp://x"]
)
@pytest.mark.asyncio
async def test_unsafe_urls_are_rejected(async_client, auth_headers, bad_url) -> None:
    for footer in (
        {"columns": [{"type": "links", "links": [{"label": {"de": "x"}, "url": bad_url}]}]},
        {"columns": [{"type": "logos", "logos": [{"src": bad_url}]}]},
        {"columns": [{"type": "logos", "logos": [{"src": "/a.png", "href": bad_url}]}]},
    ):
        response = await async_client.put("/v1/portal/config", headers=auth_headers, json={"footer": footer})
        assert response.status_code == 422, footer


@pytest.mark.asyncio
async def test_footer_asset_upload_and_download(async_client, auth_headers, tmp_path, monkeypatch) -> None:
    from katalon.config import settings

    monkeypatch.setattr(settings, "media_root", str(tmp_path))
    png = b"\\x89PNG\\r\\n\\x1a\\n" + b"0" * 64
    response = await async_client.post(
        "/v1/portal/footer-assets",
        headers=auth_headers,
        files={"file": ("dfg.png", png, "image/png")},
    )
    assert response.status_code == 201, response.text
    url = response.json()["url"]
    assert url.startswith("/portal/v1/portal/footer-assets/") and url.endswith(".png")

    download = await async_client.get(url)
    assert download.status_code == 200
    assert download.content == png
    assert download.headers["content-type"] == "image/png"

    svg = await async_client.post(
        "/v1/portal/footer-assets",
        headers=auth_headers,
        files={"file": ("x.svg", b"<svg onload='alert(1)'/>", "image/svg+xml")},
    )
    assert svg.status_code == 415
    for name in ("../secret.png", "x.svg", "not-hex.png"):
        assert (await async_client.get(f"/portal/v1/portal/footer-assets/{name}")).status_code == 404


@pytest.mark.asyncio
async def test_footer_asset_upload_requires_admin(async_client) -> None:
    response = await async_client.post(
        "/v1/portal/footer-assets", files={"file": ("a.png", b"x", "image/png")}
    )
    assert response.status_code in (401, 403)
