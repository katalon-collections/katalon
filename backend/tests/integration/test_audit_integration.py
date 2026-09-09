# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid

import pytest


@pytest.mark.asyncio
async def test_deleted_object_audit_entry_keeps_readable_label(async_client, auth_headers) -> None:
    """Regression test: the audit log for a "delete" entry used to fall back
    to a truncated UUID because the record row (and thus its idno/title) was
    already gone by the time the audit list resolved labels."""
    idno = f"AUDIT-DEL-{uuid.uuid4().hex[:8]}"
    create_response = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={"idno": idno, "status": "draft", "metadata_": {"title": "Löschbares Objekt"}},
    )
    assert create_response.status_code == 201
    object_id = create_response.json()["id"]

    delete_response = await async_client.delete(f"/v1/objects/{object_id}", headers=auth_headers)
    assert delete_response.status_code == 204

    audit_response = await async_client.get(
        f"/v1/audit?record_type=object&record_id={object_id}&action=delete", headers=auth_headers
    )
    assert audit_response.status_code == 200, audit_response.text
    entries = audit_response.json()
    assert len(entries) == 1
    assert entries[0]["record_label"] == f"Löschbares Objekt ({idno})"


@pytest.mark.asyncio
async def test_audit_search_finds_record_title_and_paginates(async_client, auth_headers) -> None:
    suffix = uuid.uuid4().hex[:8]
    title = f"Durchsuchbares Auditobjekt {suffix}"
    for number in range(2):
        response = await async_client.post(
            "/v1/objects",
            headers=auth_headers,
            json={"idno": f"AUDIT-SEARCH-{suffix}-{number}", "status": "draft", "metadata_": {"title": title}},
        )
        assert response.status_code == 201, response.text

    response = await async_client.get(
        "/v1/audit/search",
        params={"q": title, "action": "create", "page": 1, "page_size": 1},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["total"] == 2
    assert result["page"] == 1
    assert len(result["items"]) == 1
    assert result["items"][0]["record_label"].startswith(title)
