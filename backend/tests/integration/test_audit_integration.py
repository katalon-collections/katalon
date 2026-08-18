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
