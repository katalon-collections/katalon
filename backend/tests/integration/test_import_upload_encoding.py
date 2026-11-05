# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import pytest


class _Redis:
    def setex(self, *args, **kwargs) -> None:
        return None


@pytest.mark.asyncio
async def test_upload_reports_detected_encoding_and_accepts_override(
    async_client, auth_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    from katalon.api.v1 import importer

    monkeypatch.setattr(importer, "_get_redis", lambda: _Redis())
    content = "ID;Namen für Vorkommnisse\nx_1;Größe\n".encode("cp1252")

    detected = await async_client.post(
        "/v1/importer/upload", headers=auth_headers, files={"file": ("a.csv", content, "text/csv")}
    )
    assert detected.status_code == 200, detected.text
    body = detected.json()
    assert body["headers"] == ["ID", "Namen für Vorkommnisse"]
    assert (body["encoding"], body["encoding_detected"]) == ("windows-1252", "windows-1252")

    forced = await async_client.post(
        "/v1/importer/upload", headers=auth_headers,
        files={"file": ("a.csv", content, "text/csv")}, data={"encoding": "utf-8"},
    )
    forced_body = forced.json()
    assert (forced_body["encoding"], forced_body["encoding_detected"]) == ("utf-8", "windows-1252")
    assert "�" in forced_body["headers"][1]

    invalid = await async_client.post(
        "/v1/importer/upload", headers=auth_headers,
        files={"file": ("a.csv", content, "text/csv")}, data={"encoding": "koi8-r"},
    )
    assert invalid.status_code == 422
