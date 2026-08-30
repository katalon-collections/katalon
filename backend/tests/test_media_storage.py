import uuid

import pytest

from katalon.config import settings
from katalon.core.media_storage import (
    iiif_identifier,
    pyramid_storage_key,
    relative_storage_key,
    storage_key,
    storage_path,
)


def test_storage_key_shards_uuid_and_keeps_safe_original_filename() -> None:
    media_id = uuid.UUID("ab12cd34-5678-4abc-8def-0123456789ab")

    assert storage_key(media_id, "Friedas 7. Lebensjahr/DSC 01374.JPG") == (
        "ab/ab12cd34-5678-4abc-8def-0123456789ab--DSC-01374.jpg"
    )


def test_pyramid_key_stays_with_original() -> None:
    assert pyramid_storage_key("ab/id--original.jpg") == "ab/id--original_pyramid.tif"


def test_iiif_identifier_encodes_shard_separator() -> None:
    assert iiif_identifier(None, "ab/id--original.jpg") == "ab%2Fid--original.jpg"


def test_storage_path_rejects_escape_from_media_root(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "media_root", str(tmp_path))

    with pytest.raises(ValueError, match="Storage-Key"):
        storage_path("../outside.jpg")


def test_legacy_absolute_path_becomes_flat_relative_key_without_moving_file(tmp_path) -> None:
    media_root = tmp_path / "media"
    legacy_file = media_root / "aabbcc.jpg"

    assert relative_storage_key(str(legacy_file), media_root) == "aabbcc.jpg"
    assert relative_storage_key("ab/new.jpg", media_root) == "ab/new.jpg"


def test_legacy_absolute_path_outside_media_root_is_rejected(tmp_path) -> None:
    with pytest.raises(ValueError, match="nicht unter MEDIA_ROOT"):
        relative_storage_key(str(tmp_path / "outside.jpg"), tmp_path / "media")
