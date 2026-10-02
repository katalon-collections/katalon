# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import io
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image

from katalon.core.dependencies import get_current_user
from katalon.core.models import PageAsset, StaticPage, User
from katalon.database import get_db
from katalon.main import app


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (10, 10), color="red")
    img.save(buf, format="PNG")
    return buf.getvalue()


def _pdf_bytes() -> bytes:
    return b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def _mp4_bytes() -> bytes:
    # 4 bytes size, 4 bytes ftyp, 4 bytes major brand
    return b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00isommp42"


def _svg_bytes() -> bytes:
    return b"<svg xmlns='http://www.w3.org/2000/svg' width='10' height='10'><rect width='10' height='10'/></svg>"


@pytest.fixture
def mock_user():
    return User(
        id=uuid.uuid4(),
        email="admin@example.com",
        role="admin",
        hashed_password="x",
    )


@pytest.fixture
def override_auth(mock_user):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield mock_user
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_page_asset_upload_image(override_auth, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("katalon.config.settings.media_root", str(tmp_path))

    page_id = uuid.uuid4()
    page = StaticPage(
        id=page_id,
        slug="ueber-uns",
        title={"de": "Über uns"},
        content={"de": "Inhalt"},
        is_published=True,
    )

    session = AsyncMock()
    # Mock finding page
    res_page = MagicMock()
    res_page.scalar_one_or_none.return_value = page
    session.execute = AsyncMock(return_value=res_page)
    session.add = MagicMock()
    session.flush = AsyncMock()

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/v1/pages/ueber-uns/assets",
                files={"file": ("foto.png", _png_bytes(), "image/png")},
            )
        assert r.status_code == 201
        data = r.json()
        assert data["filename"] == "foto.png"
        assert data["mime_type"] == "image/png"
        assert data["page_id"] == str(page_id)
        assert "/portal/v1/pages/assets/" in data["url"]
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_page_asset_upload_pdf(override_auth, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("katalon.config.settings.media_root", str(tmp_path))

    page = StaticPage(id=uuid.uuid4(), slug="info", title={}, content={})
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none.return_value = page
    session.execute = AsyncMock(return_value=res)
    session.add = MagicMock()
    session.flush = AsyncMock()

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/v1/pages/info/assets",
                files={"file": ("ordnung.pdf", _pdf_bytes(), "application/pdf")},
            )
        assert r.status_code == 201
        assert r.json()["mime_type"] == "application/pdf"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_page_asset_upload_mp4(override_auth, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("katalon.config.settings.media_root", str(tmp_path))

    page = StaticPage(id=uuid.uuid4(), slug="video-page", title={}, content={})
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none.return_value = page
    session.execute = AsyncMock(return_value=res)
    session.add = MagicMock()
    session.flush = AsyncMock()

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/v1/pages/video-page/assets",
                files={"file": ("rundgang.mp4", _mp4_bytes(), "video/mp4")},
            )
        assert r.status_code == 201
        assert r.json()["mime_type"] == "video/mp4"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_page_asset_rejects_svg(override_auth, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("katalon.config.settings.media_root", str(tmp_path))

    page = StaticPage(id=uuid.uuid4(), slug="svg-test", title={}, content={})
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none.return_value = page
    session.execute = AsyncMock(return_value=res)

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/v1/pages/svg-test/assets",
                files={"file": ("logo.svg", _svg_bytes(), "image/svg+xml")},
            )
        assert r.status_code == 415
        assert "SVG-Dateien sind aus Sicherheitsgründen nicht als Seiten-Assets erlaubt" in r.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_page_asset_rejects_disallowed_type(override_auth, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("katalon.config.settings.media_root", str(tmp_path))

    page = StaticPage(id=uuid.uuid4(), slug="script-test", title={}, content={})
    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none.return_value = page
    session.execute = AsyncMock(return_value=res)

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/v1/pages/script-test/assets",
                files={"file": ("malicious.exe", b"MZ...", "application/x-msdownload")},
            )
        assert r.status_code == 415
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_public_serve_page_asset(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("katalon.config.settings.media_root", str(tmp_path))

    asset_id = uuid.uuid4()
    page_id = uuid.uuid4()
    filename = "test.png"
    storage_key = f"pages/{asset_id.hex[:2]}/{asset_id}--{filename}"

    dest = tmp_path / storage_key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(_png_bytes())

    asset = PageAsset(
        id=asset_id,
        page_id=page_id,
        filename=filename,
        mime_type="image/png",
        file_size=len(_png_bytes()),
        storage_key=storage_key,
        created_at=datetime.now(UTC),
    )

    session = AsyncMock()
    res = MagicMock()
    res.scalar_one_or_none.return_value = asset
    session.execute = AsyncMock(return_value=res)

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(f"/portal/v1/pages/assets/{asset_id}/{filename}")
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/png"
        assert r.headers["cache-control"] == "public, max-age=86400"
        assert r.content == _png_bytes()
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_list_page_assets(override_auth) -> None:
    page_id = uuid.uuid4()
    page = StaticPage(id=page_id, slug="gallery", title={}, content={})
    asset1 = PageAsset(
        id=uuid.uuid4(),
        page_id=page_id,
        filename="foto1.jpg",
        mime_type="image/jpeg",
        file_size=1024,
        storage_key="pages/01/foto1.jpg",
        created_at=datetime.now(UTC),
    )

    session = AsyncMock()
    # 1st execute: select StaticPage -> page
    res_page = MagicMock()
    res_page.scalar_one_or_none.return_value = page

    # 2nd execute: select PageAsset -> [asset1]
    res_assets = MagicMock()
    res_assets.scalars.return_value.all.return_value = [asset1]

    session.execute = AsyncMock(side_effect=[res_page, res_assets])

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/v1/pages/gallery/assets")
        assert r.status_code == 200
        items = r.json()
        assert len(items) == 1
        assert items[0]["filename"] == "foto1.jpg"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_delete_page_asset(override_auth, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("katalon.config.settings.media_root", str(tmp_path))

    page_id = uuid.uuid4()
    asset_id = uuid.uuid4()
    storage_key = f"pages/ab/{asset_id}--file.png"
    file_on_disk = tmp_path / storage_key
    file_on_disk.parent.mkdir(parents=True, exist_ok=True)
    file_on_disk.write_bytes(b"content")
    assert file_on_disk.exists()

    page = StaticPage(id=page_id, slug="gallery", title={}, content={})
    asset = PageAsset(
        id=asset_id,
        page_id=page_id,
        filename="file.png",
        mime_type="image/png",
        file_size=7,
        storage_key=storage_key,
        created_at=datetime.now(UTC),
    )

    session = AsyncMock()
    res_page = MagicMock()
    res_page.scalar_one_or_none.return_value = page
    res_asset = MagicMock()
    res_asset.scalar_one_or_none.return_value = asset
    session.execute = AsyncMock(side_effect=[res_page, res_asset])
    session.delete = AsyncMock()

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.delete(f"/v1/pages/gallery/assets/{asset_id}")
        assert r.status_code == 204
        assert not file_on_disk.exists()
        session.delete.assert_called_once_with(asset)
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_delete_page_deletes_storage_assets(override_auth, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("katalon.config.settings.media_root", str(tmp_path))

    page_id = uuid.uuid4()
    asset_id = uuid.uuid4()
    storage_key = f"pages/cd/{asset_id}--doc.pdf"
    file_on_disk = tmp_path / storage_key
    file_on_disk.parent.mkdir(parents=True, exist_ok=True)
    file_on_disk.write_bytes(b"pdf data")
    assert file_on_disk.exists()

    asset = PageAsset(
        id=asset_id,
        page_id=page_id,
        filename="doc.pdf",
        mime_type="application/pdf",
        file_size=8,
        storage_key=storage_key,
        created_at=datetime.now(UTC),
    )
    page = StaticPage(id=page_id, slug="doc-page", title={}, content={})
    page.assets = [asset]

    session = AsyncMock()
    res_page = MagicMock()
    res_page.scalar_one_or_none.return_value = page
    session.execute = AsyncMock(return_value=res_page)
    session.delete = AsyncMock()

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.delete("/v1/pages/doc-page")
        assert r.status_code == 204
        assert not file_on_disk.exists()
        session.delete.assert_called_once_with(page)
    finally:
        app.dependency_overrides.pop(get_db, None)

