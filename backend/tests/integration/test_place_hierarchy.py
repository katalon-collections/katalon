# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import asyncio
import uuid

import pytest
from sqlalchemy import select

from katalon import database
from katalon.core.models import Place, User


async def _make_place(client, headers, label: str, parent_id: str | None = None) -> str:
    response = await client.post(
        "/v1/places",
        headers=headers,
        json={
            "idno": f"P-{uuid.uuid4().hex[:8]}",
            "parent_id": parent_id,
            "metadata_": {"label": label},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.mark.asyncio
async def test_place_parent_cycle_delete_guard_and_object_filter(async_client, auth_headers) -> None:
    de = await _make_place(async_client, auth_headers, "Deutschland")
    mv = await _make_place(async_client, auth_headers, "Mecklenburg-Vorpommern", de)
    sn = await _make_place(async_client, auth_headers, "Schwerin", mv)
    other = await _make_place(async_client, auth_headers, "Bayern", de)

    # Missing parent and cycle are rejected.
    bad = await async_client.post(
        "/v1/places",
        headers=auth_headers,
        json={"idno": "X", "parent_id": str(uuid.uuid4()), "metadata_": {}},
    )
    assert bad.status_code == 422
    current = (await async_client.get(f"/v1/places/{de}", headers=auth_headers)).json()
    cyc = await async_client.put(
        f"/v1/places/{de}",
        headers={**auth_headers, "If-Match": str(current["version"])},
        json={"idno": current["idno"], "parent_id": sn, "metadata_": current["metadata_"]},
    )
    assert cyc.status_code == 422

    # Delete is blocked while children exist; reparent moves them up.
    blocked = await async_client.delete(f"/v1/places/{mv}", headers=auth_headers)
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["child_count"] == 1
    both = await async_client.delete(
        f"/v1/places/{mv}?cascade=true&reparent=true", headers=auth_headers
    )
    assert both.status_code == 400

    # Objects linked to a place show up for the whole subtree.
    obj = await async_client.post(
        "/v1/objects", headers=auth_headers, json={"idno": f"O-{uuid.uuid4().hex[:6]}", "metadata_": {}}
    )
    obj_id = obj.json()["id"]
    rel = await async_client.post(
        "/v1/relations",
        headers=auth_headers,
        json={
            "from_type": "object",
            "from_id": obj_id,
            "to_type": "place",
            "to_id": sn,
            "relation_type": "related_to",
        },
    )
    assert rel.status_code in (200, 201), rel.text
    in_mv = await async_client.get(f"/v1/objects?place_id={mv}", headers=auth_headers)
    assert [o["id"] for o in in_mv.json()["items"]] == [obj_id]
    only_mv = await async_client.get(
        f"/v1/objects?place_id={mv}&include_subplaces=false", headers=auth_headers
    )
    assert only_mv.json()["items"] == []
    in_other = await async_client.get(f"/v1/objects?place_id={other}", headers=auth_headers)
    assert in_other.json()["items"] == []

    moved = await async_client.delete(f"/v1/places/{mv}?reparent=true", headers=auth_headers)
    assert moved.status_code == 204
    schwerin = (await async_client.get(f"/v1/places/{sn}", headers=auth_headers)).json()
    assert schwerin["parent_id"] == de


@pytest.mark.asyncio
async def test_import_place_paths_create_hierarchy(app, monkeypatch: pytest.MonkeyPatch) -> None:
    from katalon.workers.import_tasks import import_records_task

    class _FakeRedis:
        def get(self, key: str) -> None:
            return None

    monkeypatch.setattr("redis.from_url", lambda *a, **k: _FakeRedis())
    monkeypatch.setattr(import_records_task, "update_state", lambda **kwargs: None)
    async with database.AsyncSessionLocal() as session:
        admin = await session.scalar(select(User).where(User.email == "admin@katalon.dev"))
        assert admin is not None
        user_id = str(admin.id)

    tag = uuid.uuid4().hex[:6]
    land, region = f"Land{tag}", f"Region{tag}"
    rows = [
        # Child row listed before its parent row: depth ordering must still link them.
        {"p": f"{land}>{region}>Ort A", "id": f"geo-{tag}-a"},
        {"p": f"{land}>{region}", "id": f"geo-{tag}-r"},
        {"p": f"{land}>{region}>Ort B", "id": ""},
    ]
    mapping = {
        "p": {"target": "label", "path_separator": ">"},
        "id": {"target": "__idno__"},
    }
    result = await asyncio.to_thread(
        import_records_task.run, "place", rows, mapping, idno_strategy="column", user_id=user_id
    )
    assert result["errors"] == []

    async with database.AsyncSessionLocal() as session:
        places = (
            (await session.execute(select(Place).where(Place.metadata_["label"].astext.in_(
                [land, region, "Ort A", "Ort B"]))))
            .scalars()
            .all()
        )
        by_label = {p.metadata_["label"]: p for p in places if p.idno and tag in p.idno or
                    p.metadata_["label"] in (land, region)}
        assert by_label[land].parent_id is None
        assert by_label[region].parent_id == by_label[land].id
        assert by_label[region].idno == f"geo-{tag}-r"  # the row, not an implicit duplicate
        assert by_label["Ort A"].parent_id == by_label[region].id
        assert by_label["Ort B"].parent_id == by_label[region].id
        assert by_label["Ort B"].idno == f"{land}>{region}>Ort B"  # path as fallback ID
        assert len([p for p in places if p.metadata_["label"] == region]) == 1


@pytest.mark.asyncio
async def test_portal_place_detail_shows_ancestors_children_and_subtree_objects(
    async_client, auth_headers
) -> None:
    async def public_place(label: str, parent_id: str | None = None) -> str:
        response = await async_client.post(
            "/v1/places",
            headers=auth_headers,
            json={
                "idno": f"PP-{uuid.uuid4().hex[:8]}",
                "status": "public",
                "parent_id": parent_id,
                "metadata_": {"label": label},
            },
        )
        assert response.status_code == 201, response.text
        return response.json()["id"]

    land = await public_place("Land")
    region = await public_place("Region", land)
    ort = await public_place("Ort", region)
    hidden = (
        await async_client.post(
            "/v1/places",
            headers=auth_headers,
            json={"idno": f"PH-{uuid.uuid4().hex[:6]}", "parent_id": region, "metadata_": {"label": "Entwurf"}},
        )
    ).json()["id"]
    obj = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={"idno": f"OB-{uuid.uuid4().hex[:6]}", "status": "public", "metadata_": {"label": "Fund"}},
    )
    assert obj.status_code == 201, obj.text
    obj_id = obj.json()["id"]
    await async_client.post(
        "/v1/relations",
        headers=auth_headers,
        json={
            "from_type": "object",
            "from_id": obj_id,
            "to_type": "place",
            "to_id": ort,
            "relation_type": "related_to",
        },
    )

    detail = (await async_client.get(f"/portal/v1/places/{region}")).json()
    assert [a["title"] for a in detail["ancestors"]] == ["Land"]
    assert [c["title"] for c in detail["children"]] == ["Ort"]  # draft child stays hidden
    assert detail["parent_id"] == land
    assert hidden not in [c["id"] for c in detail["children"]]

    ids = (await async_client.get(f"/portal/v1/places/{land}/object-ids")).json()
    assert ids == [obj_id]
    assert (
        await async_client.get(f"/portal/v1/places/{land}/object-ids?include_subplaces=false")
    ).json() == []
    assert (await async_client.get(f"/portal/v1/places/{hidden}/object-ids")).status_code == 404
