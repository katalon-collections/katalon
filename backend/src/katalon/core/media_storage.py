# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import asyncio
import logging
import re
import shutil
import unicodedata
import uuid
from collections.abc import AsyncIterator
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Protocol
from urllib.parse import quote

from katalon import config

if TYPE_CHECKING:
    from mypy_boto3_s3.client import S3Client

logger = logging.getLogger(__name__)


def safe_filename(filename: str) -> str:
    """Return a portable filename while retaining a recognizable original name."""
    name = Path(filename).name
    suffix = Path(name).suffix.lower()
    stem = Path(name).stem
    stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode()
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip(".-") or "upload"
    return f"{stem[:180]}{suffix[:20]}"


def storage_key(media_id: uuid.UUID, filename: str) -> str:
    """Build the relative, sharded storage key for a managed media file."""
    return f"{media_id.hex[:2]}/{media_id}--{safe_filename(filename)}"


def storage_path(key: str) -> Path:
    """Resolve a media key under MEDIA_ROOT without allowing path traversal."""
    root = Path(config.settings.media_root).resolve()
    path = (root / key).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Ungültiger Media-Storage-Key")
    return path


def relative_storage_key(value: str, media_root: str | Path | None = None) -> str:
    """Convert a legacy absolute path below MEDIA_ROOT to its relative storage key."""
    path = Path(value)
    if not path.is_absolute():
        return value
    root = Path(media_root or config.settings.media_root).resolve()
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError(f"Medienpfad liegt nicht unter MEDIA_ROOT: {value}") from exc


def pyramid_storage_key(key: str) -> str:
    path = Path(key)
    return str(path.with_name(f"{path.stem}_pyramid.tif"))


def iiif_identifier(key: str | None, fallback_key: str) -> str:
    """Use an encoded relative key so Cantaloupe receives it as one identifier."""
    return quote(key or fallback_key, safe="")


class StorageBackend(Protocol):
    """Media file storage. Implementations: local filesystem (default) and S3-compatible object storage."""

    is_local: bool

    async def put_file(self, key: str, source: Path) -> None:
        """Store the contents of a local file under key. The source file is left in place."""
        ...

    async def put_bytes(self, key: str, data: bytes) -> None:
        """Store bytes under key."""
        ...

    async def read_bytes(self, key: str) -> bytes:
        """Read the whole object. Raises FileNotFoundError when missing."""
        ...

    def stream(self, key: str) -> AsyncIterator[bytes]:
        """Yield the object in chunks. Raises FileNotFoundError when missing.

        Declared without ``async`` on purpose: implementations are async
        generator functions, so calling them already returns an AsyncIterator.
        """
        ...

    async def delete(self, *keys: str) -> None:
        """Delete objects; missing keys are ignored."""
        ...

    def exists(self, key: str) -> bool:
        """Whether an object is stored under key."""
        ...


class LocalStorage:
    """Default backend: files below MEDIA_ROOT (current behavior, unchanged)."""

    is_local = True

    def local_path(self, key: str) -> Path:
        return storage_path(key)

    async def put_file(self, key: str, source: Path) -> None:
        dest = storage_path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)

    async def put_bytes(self, key: str, data: bytes) -> None:
        dest = storage_path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)

    async def read_bytes(self, key: str) -> bytes:
        return storage_path(key).read_bytes()

    async def stream(self, key: str) -> AsyncIterator[bytes]:
        with storage_path(key).open("rb") as fh:
            while chunk := fh.read(65536):
                yield chunk

    async def delete(self, *keys: str) -> None:
        for key in keys:
            storage_path(key).unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return storage_path(key).exists()


@lru_cache(maxsize=1)
def _s3_client() -> "S3Client":
    """Build the boto3 S3 client. Cached process-wide; tests clear via cache_clear().

    Deviates from boto3 defaults on purpose — every override exists for
    compatibility with non-AWS S3 implementations (Ceph RADOSGW, MinIO, Hetzner,
    Garage):
    - request_checksum_calculation="when_required": botocore >= 1.36 otherwise
      sends x-amz-checksum-crc32 by default, which many compatible implementations
      reject with 400 Bad Request.
    - path addressing style by default: works everywhere without DNS wildcard
      setup (virtual-hosted style requires per-bucket subdomain entries on RADOSGW).
    - explicit region: RADOSGW ignores it, but SigV4 requires a value.
    """
    import boto3
    from botocore.config import Config as BotoConfig

    settings = config.settings
    verify: bool | str = settings.s3_ca_bundle or settings.s3_verify_tls
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url or None,
        aws_access_key_id=settings.s3_access_key or None,
        aws_secret_access_key=settings.s3_secret_key or None,
        region_name=settings.s3_region or "us-east-1",
        verify=verify,
        config=BotoConfig(
            signature_version="s3v4",
            s3={"addressing_style": "path" if settings.s3_force_path_style else "virtual"},
            request_checksum_calculation="when_required",
        ),
    )


class S3Storage:
    """S3-compatible object storage backend (opt-in via STORAGE_BACKEND=s3)."""

    is_local = False

    def __init__(self, client: "S3Client | None" = None) -> None:
        self._client = client

    @property
    def client(self) -> "S3Client":
        if self._client is None:
            self._client = _s3_client()
        return self._client

    @property
    def _bucket(self) -> str:
        return config.settings.s3_bucket

    async def put_file(self, key: str, source: Path) -> None:
        await asyncio.to_thread(self.client.upload_file, str(source), self._bucket, key)

    async def put_bytes(self, key: str, data: bytes) -> None:
        await asyncio.to_thread(self.client.put_object, Bucket=self._bucket, Key=key, Body=data)

    async def read_bytes(self, key: str) -> bytes:
        return await asyncio.to_thread(self._read_bytes, key)

    def _read_bytes(self, key: str) -> bytes:
        try:
            body = self.client.get_object(Bucket=self._bucket, Key=key)["Body"]
            data: bytes = body.read()
            return data
        except self.client.exceptions.NoSuchKey:
            raise FileNotFoundError(key) from None

    async def stream(self, key: str) -> AsyncIterator[bytes]:
        try:
            body = await asyncio.to_thread(self.client.get_object, Bucket=self._bucket, Key=key)
        except self.client.exceptions.NoSuchKey:
            raise FileNotFoundError(key) from None
        stream = body["Body"]
        try:
            while chunk := await asyncio.to_thread(stream.read, 65536):
                yield chunk
        finally:
            close = getattr(stream, "close", None)
            if close is not None:
                await asyncio.to_thread(close)

    async def delete(self, *keys: str) -> None:
        if not keys:
            return
        objects = [{"Key": key} for key in keys]
        await asyncio.to_thread(
            self.client.delete_objects, Bucket=self._bucket, Delete={"Objects": objects}
        )

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self._bucket, Key=key)
        except self.client.exceptions.ClientError:
            return False
        return True


def get_storage() -> StorageBackend:
    """Return the configured storage backend (local by default, S3 only when opted in)."""
    if config.settings.storage_backend == "s3":
        return S3Storage()
    return LocalStorage()
