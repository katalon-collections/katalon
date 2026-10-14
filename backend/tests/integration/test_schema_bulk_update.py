# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""PUT /v1/schema/{target_type}/bulk and GET /v1/admin/index-status."""

import uuid
from typing import Any

import pytest


async def _create_field(async_client, auth_headers, target_type: str = "object") -> dict[str, Any]:
    response = await async_client.post(
        "/v1/schema",
        headers=auth_headers,
        json={
            "target_type": target_type,
            "name": f"bulk_{uuid.uuid4().hex[:8]}",
            "label": {"de": "Bulkfeld", "en": "Bulk field"},
            "field_type": "text",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _payload(field: dict[str, Any], **changes: Any) -> dict[str, Any]:
    body = {k: v for k, v in field.items() if k not in ("children",)}
    body.update(changes)
    return body


@pytest.fixture
def reindex_requests(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []
    monkeypatch.setattr(
        "katalon.workers.reindex_state.request_bulk_reindex", lambda t, **_k: calls.append(t)
    )
    return calls


@pytest.mark.asyncio
async def test_bulk_update_saves_all_and_requests_one_reindex(
    async_client, auth_headers, reindex_requests
) -> None:
    fields = [await _create_field(async_client, auth_headers) for _ in range(3)]
    reindex_requests.clear()

    response = await async_client.put(
        "/v1/schema/object/bulk",
        headers=auth_headers,
        json=[_payload(f, is_public=not f["is_public"], sort_order=50 + i)
              for i, f in enumerate(fields)],
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert [f["id"] for f in body] == [f["id"] for f in fields]
    assert all(f["is_public"] != old["is_public"] for f, old in zip(body, fields, strict=True))
    assert reindex_requests == ["object"]


@pytest.mark.asyncio
async def test_bulk_update_facet_only_needs_no_reindex(
    async_client, auth_headers, reindex_requests
) -> None:
    fields = [await _create_field(async_client, auth_headers) for _ in range(2)]
    reindex_requests.clear()

    response = await async_client.put(
        "/v1/schema/object/bulk",
        headers=auth_headers,
        json=[_payload(f, is_facet=True) for f in fields],
    )

    assert response.status_code == 200, response.text
    assert all(f["is_facet"] for f in response.json())
    assert reindex_requests == []


@pytest.mark.asyncio
async def test_bulk_update_is_all_or_nothing(async_client, auth_headers, reindex_requests) -> None:
    good = await _create_field(async_client, auth_headers)
    foreign = await _create_field(async_client, auth_headers, target_type="place")
    reindex_requests.clear()

    response = await async_client.put(
        "/v1/schema/object/bulk",
        headers=auth_headers,
        json=[_payload(good, sort_order=77), _payload(foreign, sort_order=77)],
    )
    assert response.status_code == 422

    listed = await async_client.get("/v1/schema/object", headers=auth_headers)
    stored = next(f for f in listed.json() if f["id"] == good["id"])
    assert stored["sort_order"] == good["sort_order"]
    assert reindex_requests == []


@pytest.mark.asyncio
async def test_index_status_reports_running_job(
    async_client, auth_headers, fake_reindex_redis
) -> None:
    import fakeredis

    from katalon.workers import reindex_state

    client = fakeredis.FakeRedis(server=fake_reindex_redis, decode_responses=True)
    progress = reindex_state.ProgressReporter(client, "object", "task-1")
    progress.update(force=True, total=1000, built=250, indexed=250)
    lock = client.lock(reindex_state.RUN_LOCK_KEY, timeout=60, thread_local=False)
    assert lock.acquire(blocking=False)
    client.set(reindex_state.queued_key("object"), "x")
    client.set(reindex_state.dirty_key("object"), "x")

    response = await async_client.get("/v1/admin/index-status", headers=auth_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["available"] is True
    obj = body["types"]["object"]
    assert obj["state"] == "running"
    assert (obj["total"], obj["built"]) == (1000, 250)
    assert obj["queued"] is True
    assert obj["pending_changes"] is True
    assert obj["eta_seconds"] is not None
    assert body["types"]["place"]["state"] == "idle"
    assert body["full_rebuild"]["state"] == "idle"

    # Lease gone while progress still says running → the worker died.
    lock.release()
    response = await async_client.get("/v1/admin/index-status", headers=auth_headers)
    assert response.json()["types"]["object"]["state"] == "failed"
