# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Tests for media Celery task internals."""
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from katalon.integrations.cantaloupe import CantaloupeError
from katalon.workers.media_tasks import _make_pyramid_tiff, _process, _set_error

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(media_file=None):
    result = MagicMock()
    result.scalar_one_or_none.return_value = media_file
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    return session


def _make_media_file(**kwargs):
    media = MagicMock()
    media.id = kwargs.get("id", uuid.uuid4())
    media.storage_key = kwargs.get("storage_key", "ab/test.jpg")
    media.status = kwargs.get("status", "pending")
    media.iiif_manifest = kwargs.get("iiif_manifest", None)
    media.iiif_storage_key = kwargs.get("iiif_storage_key", None)
    return media


def _patch_worker_session(session):
    """Return a context manager that patches _worker_session to yield *session*."""

    class FakeAsyncContextManager:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *args):
            pass

    class FakeSessionMaker:
        def __call__(self):
            return FakeAsyncContextManager()

    return patch("katalon.workers.media_tasks._worker_session", return_value=FakeSessionMaker())


# ---------------------------------------------------------------------------
# _process
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_fetches_info_builds_manifest_sets_ready() -> None:
    media = _make_media_file()
    session = _make_session(media)

    fake_manifest = {"type": "Manifest", "items": []}

    with _patch_worker_session(session):
        fetch_patch = patch(
            "katalon.integrations.cantaloupe.fetch_image_info",
            AsyncMock(return_value=(1200, 800)),
        )
        build_patch = patch(
            "katalon.integrations.cantaloupe.build_manifest",
            return_value=fake_manifest,
        )
        with fetch_patch, build_patch:
            result = await _process(media.id)

    assert result["status"] == "ok"
    assert result["manifest"] == fake_manifest
    assert media.status == "ready"
    assert media.iiif_manifest == fake_manifest
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_process_uses_pyramid_filename_when_conversion_succeeds() -> None:
    media = _make_media_file(storage_key="ab/test.jpg")
    session = _make_session(media)

    with _patch_worker_session(session):
        with (
            patch(
                "katalon.workers.media_tasks._make_pyramid_tiff",
                return_value=Path("/anywhere/test_pyramid.tif"),
            ),
            patch(
                "katalon.integrations.cantaloupe.fetch_image_info",
                AsyncMock(return_value=(1200, 800)),
            ) as fetch_mock,
            patch("katalon.integrations.cantaloupe.build_manifest", return_value={}),
        ):
            await _process(media.id)

    fetch_mock.assert_awaited_with("ab%2Ftest_pyramid.tif")
    assert media.iiif_storage_key == "ab/test_pyramid.tif"


@pytest.mark.asyncio
async def test_process_falls_back_to_original_when_pyramid_conversion_fails() -> None:
    media = _make_media_file(storage_key="ab/test.jpg")
    session = _make_session(media)

    with _patch_worker_session(session):
        with (
            patch("katalon.workers.media_tasks._make_pyramid_tiff", return_value=None),
            patch(
                "katalon.integrations.cantaloupe.fetch_image_info",
                AsyncMock(return_value=(1200, 800)),
            ) as fetch_mock,
            patch("katalon.integrations.cantaloupe.build_manifest", return_value={}),
        ):
            await _process(media.id)

    fetch_mock.assert_awaited_with("ab%2Ftest.jpg")
    assert media.iiif_storage_key is None


@pytest.mark.asyncio
async def test_process_sets_error_on_cantaloupe_error() -> None:
    media = _make_media_file()
    session = _make_session(media)

    with _patch_worker_session(session):
        with patch(
            "katalon.integrations.cantaloupe.fetch_image_info",
            AsyncMock(side_effect=CantaloupeError("unreadable image")),
        ):
            result = await _process(media.id)

    assert result["status"] == "error"
    assert "unreadable image" in result["detail"]
    assert media.status == "error"
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_process_raises_when_media_not_found() -> None:
    session = _make_session(media_file=None)

    with _patch_worker_session(session):
        with pytest.raises(ValueError, match="not found"):
            await _process(uuid.uuid4())


# ---------------------------------------------------------------------------
# _make_pyramid_tiff
# ---------------------------------------------------------------------------


def test_make_pyramid_tiff_creates_tiled_pyramid_tiff(tmp_path: Path) -> None:
    pyvips = pytest.importorskip("pyvips")

    source_path = tmp_path / "source.jpg"
    pyvips.Image.black(256, 256).jpegsave(str(source_path))

    dest_path = _make_pyramid_tiff(source_path)

    assert dest_path is not None
    assert dest_path == source_path.with_name("source_pyramid.tif")
    assert dest_path.exists()

    result = pyvips.Image.new_from_file(str(dest_path))
    assert result.get("vips-loader") == "tiffload"
    assert result.get("n-pages") > 1
    # tile-width metadata is only exposed by libvips >= 8.18; older versions
    # (e.g. CI's apt package) still write tiled TIFFs, they just don't report it.
    if (pyvips.base.version(0), pyvips.base.version(1)) >= (8, 18):
        assert result.get("tile-width") > 0


def test_make_pyramid_tiff_returns_none_for_unreadable_source(tmp_path: Path) -> None:
    pytest.importorskip("pyvips")

    source_path = tmp_path / "not-an-image.jpg"
    source_path.write_bytes(b"not a real image")

    assert _make_pyramid_tiff(source_path) is None
    assert not source_path.with_name("not-an-image_pyramid.tif").exists()


# ---------------------------------------------------------------------------
# _set_error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_error_sets_status_when_media_exists() -> None:
    media = _make_media_file()
    session = _make_session(media)

    with _patch_worker_session(session):
        await _set_error(media.id, "something went wrong")

    assert media.status == "error"
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_set_error_does_nothing_when_media_not_found() -> None:
    session = _make_session(media_file=None)

    with _patch_worker_session(session):
        await _set_error(uuid.uuid4(), "something went wrong")

    session.commit.assert_not_awaited()
