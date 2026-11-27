# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import uuid

import pytest


@pytest.mark.asyncio
async def test_required_field_lifecycle_marks_and_clears_existing_records(
    async_client, auth_headers
) -> None:
    suffix = uuid.uuid4().hex[:8]
    field_name = f"req_field_{suffix}"
    opt_field_name = f"opt_to_req_{suffix}"

    # Create two existing records before adding any new required field.
    rec_missing_resp = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"INC-MISS-{suffix}",
            "status": "internal",
            "metadata_": {"label": "Ohne neues Pflichtfeld"},
        },
    )
    assert rec_missing_resp.status_code == 201, rec_missing_resp.text
    rec_missing = rec_missing_resp.json()
    assert rec_missing["schema_incomplete"] is False
    orig_version = rec_missing["version"]
    orig_updated_at = rec_missing["updated_at"]
    orig_metadata = dict(rec_missing["metadata_"])

    rec_complete_resp = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"INC-OK-{suffix}",
            "status": "internal",
            "metadata_": {"label": "Mit Wert", field_name: "bereits vorhanden"},
        },
    )
    assert rec_complete_resp.status_code == 201, rec_complete_resp.text
    rec_complete = rec_complete_resp.json()

    # 1. Creating a new required field marks records missing it, without mutating record content.
    create_req = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "object",
            "name": field_name,
            "label": {"de": "Neues Pflichtfeld", "en": "New required field"},
            "field_type": "text",
            "is_required": True,
        },
    )
    assert create_req.status_code == 201, create_req.text
    req_field_id = create_req.json()["id"]

    fetched_missing = (
        await async_client.get(f"/v1/objects/{rec_missing['id']}", headers=auth_headers)
    ).json()
    assert fetched_missing["schema_incomplete"] is True
    assert fetched_missing["metadata_"] == orig_metadata
    assert fetched_missing["version"] == orig_version
    assert fetched_missing["updated_at"] == orig_updated_at

    fetched_complete = (
        await async_client.get(f"/v1/objects/{rec_complete['id']}", headers=auth_headers)
    ).json()
    assert fetched_complete["schema_incomplete"] is False

    # 2. Listing filter returns only incomplete records; anonymous access masks the marker.
    list_incomplete = (
        await async_client.get(
            "/v1/objects",
            headers=auth_headers,
            params={"schema_incomplete": "true", "q": suffix},
        )
    ).json()
    assert [item["id"] for item in list_incomplete["items"]] == [rec_missing["id"]]

    # 3. Saving and publishing remain strictly blocked until required field is supplied.
    blocked_save = await async_client.put(
        f"/v1/objects/{rec_missing['id']}",
        headers={**auth_headers, "If-Match": str(orig_version)},
        json={
            "idno": rec_missing["idno"],
            "status": "internal",
            "metadata_": {"label": "Noch unvollständig"},
        },
    )
    assert blocked_save.status_code == 422

    blocked_publish = await async_client.post(
        f"/v1/objects/{rec_missing['id']}/publish",
        headers=auth_headers,
    )
    assert blocked_publish.status_code == 422

    # 4. Filling the missing required field and saving clears the marker.
    fixed_save = await async_client.put(
        f"/v1/objects/{rec_missing['id']}",
        headers={**auth_headers, "If-Match": str(orig_version)},
        json={
            "idno": rec_missing["idno"],
            "status": "internal",
            "metadata_": {"label": "Jetzt vollständig", field_name: "nachgepflegt"},
        },
    )
    assert fixed_save.status_code == 200, fixed_save.text
    assert fixed_save.json()["schema_incomplete"] is False

    # 5. Switching an existing optional field to required marks records, switching back clears it.
    create_opt = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "object",
            "name": opt_field_name,
            "label": {"de": "Optionales Feld"},
            "field_type": "text",
            "is_required": False,
        },
    )
    assert create_opt.status_code == 201, create_opt.text
    opt_field = create_opt.json()

    make_required = await async_client.put(
        f"/v1/schema/{opt_field['id']}",
        headers=auth_headers,
        json={
            "target_type": "object",
            "name": opt_field_name,
            "label": {"de": "Optionales Feld"},
            "field_type": "text",
            "is_required": True,
        },
    )
    assert make_required.status_code == 200, make_required.text
    assert (
        await async_client.get(f"/v1/objects/{rec_missing['id']}", headers=auth_headers)
    ).json()["schema_incomplete"] is True

    make_optional_again = await async_client.put(
        f"/v1/schema/{opt_field['id']}",
        headers=auth_headers,
        json={
            "target_type": "object",
            "name": opt_field_name,
            "label": {"de": "Optionales Feld"},
            "field_type": "text",
            "is_required": False,
        },
    )
    assert make_optional_again.status_code == 200, make_optional_again.text
    assert (
        await async_client.get(f"/v1/objects/{rec_missing['id']}", headers=auth_headers)
    ).json()["schema_incomplete"] is False

    # Cleanup test fields so other tests in the session are unaffected.
    assert (await async_client.delete(f"/v1/schema/{req_field_id}", headers=auth_headers)).status_code == 204
    assert (await async_client.delete(f"/v1/schema/{opt_field['id']}", headers=auth_headers)).status_code == 204


@pytest.mark.asyncio
async def test_subtype_scoped_required_field_only_marks_matching_subtype(
    async_client, auth_headers
) -> None:
    suffix = uuid.uuid4().hex[:8]
    sub_a = f"sub_a_{suffix}"
    sub_b = f"sub_b_{suffix}"
    for sub in (sub_a, sub_b):
        resp = await async_client.post(
            "/v1/record-subtypes",
            headers=auth_headers,
            json={"primary_type": "object", "name": sub, "label": {"de": sub}},
        )
        assert resp.status_code == 201, resp.text

    obj_a = (
        await async_client.post(
            "/v1/objects",
            headers=auth_headers,
            json={
                "idno": f"SUB-A-{suffix}",
                "object_type": sub_a,
                "status": "public",
                "metadata_": {"label": "A"},
            },
        )
    ).json()
    obj_b = (
        await async_client.post(
            "/v1/objects",
            headers=auth_headers,
            json={
                "idno": f"SUB-B-{suffix}",
                "object_type": sub_b,
                "status": "public",
                "metadata_": {"label": "B"},
            },
        )
    ).json()

    req_field = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": "object",
            "target_subtype": sub_a,
            "name": f"only_a_{suffix}",
            "label": {"de": "Nur für A"},
            "field_type": "text",
            "is_required": True,
        },
    )
    assert req_field.status_code == 201, req_field.text
    field_id = req_field.json()["id"]

    # Staff sees schema_incomplete=True on obj_a, False on obj_b.
    assert (await async_client.get(f"/v1/objects/{obj_a['id']}", headers=auth_headers)).json()[
        "schema_incomplete"
    ] is True
    assert (await async_client.get(f"/v1/objects/{obj_b['id']}", headers=auth_headers)).json()[
        "schema_incomplete"
    ] is False

    # The public projection leaves out the internal marker.
    public_obj = await async_client.get(f"/portal/v1/objects/{obj_a['id']}")
    assert public_obj.status_code == 200, public_obj.text
    assert "schema_incomplete" not in public_obj.json()

    # Deleting the required field clears schema_incomplete; restoring re-marks it.
    assert (await async_client.delete(f"/v1/schema/{field_id}", headers=auth_headers)).status_code == 204
    assert (await async_client.get(f"/v1/objects/{obj_a['id']}", headers=auth_headers)).json()[
        "schema_incomplete"
    ] is False

    assert (
        await async_client.post(f"/v1/schema/{field_id}/restore", headers=auth_headers)
    ).status_code == 200
    assert (await async_client.get(f"/v1/objects/{obj_a['id']}", headers=auth_headers)).json()[
        "schema_incomplete"
    ] is True

    # Batch edit filling the missing field clears schema_incomplete.
    batch_resp = await async_client.post(
        "/v1/batch/object",
        headers=auth_headers,
        json={
            "operation": {"type": "set_field", "field": f"only_a_{suffix}", "value": "ergänzt"},
            "filters": {"object_type": sub_a, "schema_incomplete": True},
        },
    )
    assert batch_resp.status_code == 200, batch_resp.text
    assert batch_resp.json()["affected"] == 1
    assert (await async_client.get(f"/v1/objects/{obj_a['id']}", headers=auth_headers)).json()[
        "schema_incomplete"
    ] is False

    # Cleanup
    assert (await async_client.delete(f"/v1/schema/{field_id}", headers=auth_headers)).status_code == 204
