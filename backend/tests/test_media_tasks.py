"""Tests for media Celery task internals."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from katalon.integrations.cantaloupe import CantaloupeError
from katalon.workers.media_tasks import _process, _set_error

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
    media.file_path = kwargs.get("file_path", "/media/test.jpg")
    media.status = kwargs.get("status", "pending")
    media.iiif_manifest = kwargs.get("iiif_manifest", None)
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
