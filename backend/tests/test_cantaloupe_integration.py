# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Tests for Cantaloupe IIIF integration helpers."""
from unittest.mock import patch

import pytest

from katalon.integrations.cantaloupe import (
    CantaloupeError,
    build_manifest,
    build_object_manifest,
    fetch_image_info,
)


class _Response:
    def __init__(self, data: dict, status: int = 200) -> None:
        self.status_code = status
        self._data = data

    def json(self) -> dict:
        return self._data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


def _http(data: dict, status: int = 200):
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def get(self, *args, **kwargs) -> _Response:
            return _Response(data, status)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            pass

    return FakeAsyncClient


# ── fetch_image_info ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_image_info_returns_dimensions() -> None:
    data = {"width": 1200, "height": 800}
    with patch("katalon.integrations.cantaloupe.httpx.AsyncClient", _http(data)):
        width, height = await fetch_image_info("test.jpg")
    assert width == 1200
    assert height == 800


@pytest.mark.asyncio
async def test_fetch_image_info_returns_none_on_5xx() -> None:
    with patch("katalon.integrations.cantaloupe.httpx.AsyncClient", _http({}, status=503)):
        width, height = await fetch_image_info("test.jpg")
    assert width is None
    assert height is None


@pytest.mark.asyncio
async def test_fetch_image_info_raises_on_4xx() -> None:
    with patch("katalon.integrations.cantaloupe.httpx.AsyncClient", _http({}, status=404)):
        with pytest.raises(CantaloupeError):
            await fetch_image_info("missing.jpg")


# ── build_manifest ────────────────────────────────────────────────────────────


def test_build_manifest_creates_valid_single_canvas_manifest() -> None:
    import uuid

    media_id = uuid.uuid4()
    manifest = build_manifest(media_id, "photo.jpg", width=1200, height=800)

    assert manifest["@context"] == "http://iiif.io/api/presentation/3/context.json"
    assert manifest["type"] == "Manifest"
    assert len(manifest["items"]) == 1

    canvas = manifest["items"][0]
    assert canvas["type"] == "Canvas"
    assert canvas["width"] == 1200
    assert canvas["height"] == 800

    annotation_page = canvas["items"][0]
    annotation = annotation_page["items"][0]
    assert annotation["type"] == "Annotation"
    assert annotation["motivation"] == "painting"
    assert annotation["body"]["type"] == "Image"
    assert annotation["body"]["service"][0]["type"] == "ImageService3"
    assert annotation["body"]["service"][0]["profile"] == "level2"


def test_build_manifest_without_dimensions() -> None:
    import uuid

    media_id = uuid.uuid4()
    manifest = build_manifest(media_id, "photo.jpg")

    canvas = manifest["items"][0]
    assert "width" not in canvas
    assert "height" not in canvas


# ── build_object_manifest ─────────────────────────────────────────────────────


def test_build_object_manifest_multi_canvas_with_metadata() -> None:
    from unittest.mock import MagicMock

    obj = MagicMock()
    obj.idno = "OBJ-001"
    obj.metadata_ = {
        "title": [{"value": "Straße in Marrakesch", "lang": "de"}],
        "description": [{"value": "Eine alte Straße", "lang": "de"}],
    }

    fd_title = MagicMock()
    fd_title.name = "title"
    fd_title.label = {"de": "Titel", "en": "Title"}

    fd_desc = MagicMock()
    fd_desc.name = "description"
    fd_desc.label = {"de": "Beschreibung", "en": "Description"}

    media_items = [
        ("img1.jpg", {"width": 1200, "height": 800}),
        ("img2.jpg", {"width": 600, "height": 400}),
    ]

    manifest = build_object_manifest(
        "http://test/manifest",
        media_items,
        obj=obj,
        field_defs=[fd_title, fd_desc],
        homepage_url="http://test/objects/123",
    )

    assert manifest["type"] == "Manifest"
    assert len(manifest["items"]) == 2

    assert manifest["label"] == {"none": ["Straße in Marrakesch"]}
    assert manifest["summary"] == {"none": ["Eine alte Straße"]}
    expected_homepage = [{"id": "http://test/objects/123", "type": "Text", "format": "text/html"}]
    assert manifest["homepage"] == expected_homepage
    assert manifest["requiredStatement"]["value"] == {"none": ["OBJ-001"]}

    assert "metadata" in manifest
    meta_labels = [str(m["label"]) for m in manifest["metadata"]]
    assert any("Titel" in m for m in meta_labels)
    assert any("Beschreibung" in m for m in meta_labels)


def test_build_object_manifest_falls_back_to_idno_for_label() -> None:
    from unittest.mock import MagicMock

    obj = MagicMock()
    obj.idno = "OBJ-042"
    obj.metadata_ = {}

    manifest = build_object_manifest(
        "http://test/manifest",
        [("img.jpg", None)],
        obj=obj,
    )

    assert manifest["label"] == {"none": ["OBJ-042"]}


def test_build_object_manifest_no_obj() -> None:
    manifest = build_object_manifest(
        "http://test/manifest",
        [("img.jpg", None)],
    )

    assert manifest["type"] == "Manifest"
    assert len(manifest["items"]) == 1
    assert "label" not in manifest
