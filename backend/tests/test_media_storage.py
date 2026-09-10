# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import io
import uuid

import pytest

from katalon.config import settings
from katalon.core.media_storage import (
    LocalStorage,
    S3Storage,
    _s3_client,
    get_storage,
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


# ---------------------------------------------------------------------------
# Backend selection (opt-in)
# ---------------------------------------------------------------------------


def test_get_storage_defaults_to_local() -> None:
    assert settings.storage_backend == "local"
    assert isinstance(get_storage(), LocalStorage)
    assert get_storage().is_local


def test_get_storage_returns_s3_only_when_opted_in(monkeypatch) -> None:
    monkeypatch.setattr(settings, "storage_backend", "s3")
    storage = get_storage()
    assert isinstance(storage, S3Storage)
    assert not storage.is_local


# ---------------------------------------------------------------------------
# LocalStorage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_local_storage_roundtrip_and_delete(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "media_root", str(tmp_path))
    storage = LocalStorage()
    source = tmp_path / "source.jpg"
    source.write_bytes(b"pixels")

    await storage.put_file("ab/test.jpg", source)
    assert source.exists()  # put_file must not consume the source
    assert await storage.read_bytes("ab/test.jpg") == b"pixels"
    assert [c async for c in storage.stream("ab/test.jpg")] == [b"pixels"]
    assert storage.exists("ab/test.jpg")

    await storage.delete("ab/test.jpg")
    assert not storage.exists("ab/test.jpg")
    await storage.delete("ab/missing.jpg")  # missing keys are ignored


# ---------------------------------------------------------------------------
# S3Storage (botocore Stubber — no network)
# ---------------------------------------------------------------------------


def _stubbed_s3(monkeypatch):
    """S3Storage with a Stubber-wrapped client; returns (storage, stubber)."""
    import boto3
    from botocore.config import Config as BotoConfig
    from botocore.stub import Stubber

    monkeypatch.setattr(settings, "s3_bucket", "test-bucket")
    client = boto3.client(
        "s3",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1",
        endpoint_url="https://gateway.invalid",
        config=BotoConfig(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            request_checksum_calculation="when_required",
        ),
    )
    return S3Storage(client=client), Stubber(client)


@pytest.mark.asyncio
async def test_s3_storage_put_and_read_bytes(monkeypatch, tmp_path) -> None:
    storage, stubber = _stubbed_s3(monkeypatch)
    stubber.add_response(
        "put_object", {}, expected_params={"Bucket": "test-bucket", "Key": "ab/test.jpg", "Body": b"pixels"}
    )
    stubber.add_response(
        "get_object",
        {"Body": _streaming_body(b"pixels")},
        expected_params={"Bucket": "test-bucket", "Key": "ab/test.jpg"},
    )
    stubber.add_response(
        "head_object", {}, expected_params={"Bucket": "test-bucket", "Key": "ab/test.jpg"}
    )
    with stubber:
        await storage.put_bytes("ab/test.jpg", b"pixels")
        assert await storage.read_bytes("ab/test.jpg") == b"pixels"
        assert storage.exists("ab/test.jpg")


@pytest.mark.asyncio
async def test_s3_storage_put_file_streams_and_delete(monkeypatch, tmp_path) -> None:
    from unittest.mock import MagicMock

    storage, stubber = _stubbed_s3(monkeypatch)
    source = tmp_path / "source.jpg"
    source.write_bytes(b"pixels")
    # upload_file (managed transfer) sends a ReadFileChunk, not raw bytes, so the
    # Stubber can't match Body — assert the call args on a wrapping mock instead.
    upload_mock = MagicMock(wraps=storage.client.upload_file)
    storage.client.upload_file = upload_mock
    stubber.add_response("put_object", {})  # expected_params=None: skip Body validation
    stubber.add_response(
        "get_object",
        {"Body": _streaming_body(b"pixels")},
        expected_params={"Bucket": "test-bucket", "Key": "ab/test.jpg"},
    )
    stubber.add_response(
        "delete_objects",
        {},
        expected_params={
            "Bucket": "test-bucket",
            "Delete": {"Objects": [{"Key": "ab/test.jpg"}, {"Key": "ab/test_pyramid.tif"}]},
        },
    )
    with stubber:
        await storage.put_file("ab/test.jpg", source)
        upload_mock.assert_called_once_with(str(source), "test-bucket", "ab/test.jpg")
        assert [c async for c in storage.stream("ab/test.jpg")] == [b"pixels"]
        await storage.delete("ab/test.jpg", "ab/test_pyramid.tif")


@pytest.mark.asyncio
async def test_s3_storage_missing_key_raises_file_not_found(monkeypatch) -> None:
    storage, stubber = _stubbed_s3(monkeypatch)
    stubber.add_client_error("get_object", "NoSuchKey", http_status_code=404)
    stubber.add_client_error("head_object", "404", http_status_code=404)
    with stubber:
        with pytest.raises(FileNotFoundError):
            await storage.read_bytes("ab/missing.jpg")
        assert not storage.exists("ab/missing.jpg")


def _streaming_body(data: bytes):
    from botocore.response import StreamingBody

    return StreamingBody(io.BytesIO(data), len(data))


# ---------------------------------------------------------------------------
# Client construction — RADOSGW / S3-compatible portability guards
# ---------------------------------------------------------------------------


def test_s3_client_disables_default_checksum_and_uses_path_style(monkeypatch) -> None:
    """botocore >= 1.36 sends x-amz-checksum-crc32 by default, which RADOSGW and
    other compatible implementations reject with 400. Path style works without
    DNS wildcard setup. Both overrides must stay."""
    monkeypatch.setattr(settings, "s3_endpoint_url", "https://gateway.invalid")
    monkeypatch.setattr(settings, "s3_access_key", "test")
    monkeypatch.setattr(settings, "s3_secret_key", "test")
    monkeypatch.setattr(settings, "s3_region", "us-east-1")
    monkeypatch.setattr(settings, "s3_force_path_style", True)
    monkeypatch.setattr(settings, "s3_ca_bundle", "")
    monkeypatch.setattr(settings, "s3_verify_tls", True)
    _s3_client.cache_clear()

    client = _s3_client()
    try:
        assert client.meta.config.s3["addressing_style"] == "path"
        assert client.meta.config.signature_version == "s3v4"
        assert client.meta.config.request_checksum_calculation == "when_required"
    finally:
        _s3_client.cache_clear()
