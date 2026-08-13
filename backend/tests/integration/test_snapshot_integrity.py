import uuid

import pytest


@pytest.mark.parametrize(
    ("route", "type_field", "type_value"),
    [
        ("entities", None, None),
        ("places", None, None),
        ("occurrences", None, None),
        ("procedures", "procedure_type", "acquisition"),
    ],
)
async def test_snapshot_restore_requires_if_match_for_all_record_types(
    async_client,
    auth_headers,
    route: str,
    type_field: str | None,
    type_value: str | None,
) -> None:
    payload = {
        "idno": f"SNAP-{uuid.uuid4().hex[:12]}",
        "status": "draft",
        "metadata_": {},
    }
    if type_field and type_value:
        payload[type_field] = type_value
    created = await async_client.post(
        f"/v1/{route}",
        headers=auth_headers,
        json=payload,
    )
    assert created.status_code == 201, created.text
    record = created.json()
    snapshot = await async_client.post(
        f"/v1/{route}/{record['id']}/snapshots",
        headers=auth_headers,
        json={"label": "restore contract"},
    )
    assert snapshot.status_code == 201, snapshot.text

    restore_url = f"/v1/{route}/{record['id']}/snapshots/{snapshot.json()['id']}/restore"
    missing = await async_client.post(restore_url, headers=auth_headers)
    assert missing.status_code == 428
    restored = await async_client.post(
        restore_url,
        headers={**auth_headers, "If-Match": str(record["version"])},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["version"] == record["version"] + 1
