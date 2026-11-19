# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid

import pytest
from httpx import AsyncClient

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("record_type", "route"),
    [("collection", "collections"), ("storage_location", "storage-locations")],
)
async def test_file_field_saves_on_update(
    async_client: AsyncClient,
    auth_headers: dict[str, str],
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    record_type: str,
    route: str,
) -> None:
    monkeypatch.setattr("katalon.config.settings.media_root", str(tmp_path))
    field = f"skizze_{uuid.uuid4().hex[:8]}"
    res = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={"target_type": record_type, "name": field, "field_type": "file", "is_public": False},
    )
    assert res.status_code == 201, res.text

    idno = f"T-{uuid.uuid4().hex[:10]}"
    base_md = {"label": "Testlager", "idno": idno}
    created = await async_client.post(
        f"/v1/{route}",
        headers=auth_headers,
        json={"idno": idno, "status": "draft", "metadata_": base_md},
    )
    assert created.status_code == 201, created.text
    rec = created.json()

    up = await async_client.post(
        f"/v1/attachments/{record_type}/{rec['id']}",
        headers=auth_headers,
        files={"file": ("Anfahrt.pdf", PDF, "application/pdf")},
    )
    assert up.status_code == 201, up.text

    updated = await async_client.put(
        f"/v1/{route}/{rec['id']}",
        headers={**auth_headers, "If-Match": str(rec["version"])},
        json={"idno": rec["idno"], "status": "draft", "metadata_": {**base_md, field: {"id": up.json()["id"]}}},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["metadata_"][field]["filename"] == "Anfahrt.pdf"
