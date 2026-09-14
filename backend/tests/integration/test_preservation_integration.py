# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import io
import uuid
import zipfile

import pytest

from katalon.core.models import AuditLog, MediaFile, Object


@pytest.mark.asyncio
async def test_preservation_bag_download(async_client, auth_headers, monkeypatch, tmp_path):
    from katalon.config import settings
    from katalon.database import AsyncSessionLocal

    media_root = tmp_path / "media"
    media_root.mkdir()
    monkeypatch.setattr(settings, "media_root", str(media_root))

    async with AsyncSessionLocal() as session:
        obj = Object(idno="PRES-1", metadata_={"title": "Archivwürdig"})
        session.add(obj)
        await session.flush()

        media_id = uuid.uuid4()
        key = f"{media_id.hex[:2]}/{media_id}--scan.tif"
        (media_root / key.split("/")[0]).mkdir(exist_ok=True)
        (media_root / key).write_bytes(b"tiff-bytes")
        session.add(MediaFile(
            id=media_id,
            object_id=obj.id,
            filename="scan.tif",
            mime_type="image/tiff",
            storage_key=key,
            status="ready",
            license_uri="https://creativecommons.org/publicdomain/mark/1.0/",
        ))
        session.add(AuditLog(
            record_type="object",
            record_id=obj.id,
            action="create",
            changed_fields={"metadata": {"title": None}},
        ))
        await session.commit()
        object_id = obj.id

    response = await async_client.get(
        f"/v1/preservation/objects/{object_id}/bag", headers=auth_headers
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert 'filename="preservation-PRES-1.zip"' in response.headers["content-disposition"]

    zf = zipfile.ZipFile(io.BytesIO(response.content))
    names = set(zf.namelist())
    assert "bagit.txt" in names
    assert "bag-info.txt" in names
    assert "manifest-sha256.txt" in names
    assert "data/metadata/descriptive.xml" in names
    assert "data/metadata/mets.xml" in names
    assert "data/metadata/premis.xml" in names
    master_entries = [n for n in names if n.startswith("data/files/master/")]
    assert len(master_entries) == 1 and master_entries[0].endswith("--scan.tif")
    assert zf.read(master_entries[0]) == b"tiff-bytes"

    manifest = zf.read("manifest-sha256.txt").decode()
    assert master_entries[0] in manifest

    bag_info = zf.read("bag-info.txt").decode()
    assert "External-Identifier: PRES-1" in bag_info

    premis = zf.read("data/metadata/premis.xml").decode()
    assert "creation" in premis


@pytest.mark.asyncio
async def test_preservation_bag_unknown_object_returns_404(async_client, auth_headers):
    response = await async_client.get(
        f"/v1/preservation/objects/{uuid.uuid4()}/bag", headers=auth_headers
    )
    assert response.status_code == 404
