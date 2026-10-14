# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from katalon.core.models import MediaFile
from katalon.services.search_service import _load_primary_media


def _media(mime: str, key: str, pyramid: str | None = None) -> MediaFile:
    return MediaFile(
        id=uuid.uuid4(), object_id=uuid.uuid4(), filename=key, mime_type=mime,
        storage_key=key, iiif_storage_key=pyramid, status="ready", width=10, height=20,
    )


@pytest.mark.asyncio
async def test_primary_media_carries_iiif_identifier_of_first_image() -> None:
    pdf = _media("application/pdf", "aa/doc.pdf")
    image = _media("image/tiff", "bb/scan.tif", pyramid="bb/scan.pyramid.tif")
    result = MagicMock()
    result.scalars.return_value.all.return_value = [pdf, image]
    db = AsyncMock()
    db.execute.return_value = result

    info = await _load_primary_media(uuid.uuid4(), db)

    assert info == {
        "primary_media_id": str(image.id),
        # Pyramid preferred, URL-encoded as one IIIF identifier.
        "primary_media_iiif": "bb%2Fscan.pyramid.tif",
        "media_width": 10,
        "media_height": 20,
    }
