# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid

import pytest

from katalon import database
from katalon.core.models import Collection
from katalon.services.collection_service import (
    get_collection_subtree_ids,
    get_collection_subtree_titles,
)


@pytest.mark.asyncio
async def test_collection_subtree_ids(app) -> None:
    async with database.AsyncSessionLocal() as db_session:
        # 1. Create root collection
        root = Collection(
            idno=f"COL-ROOT-{uuid.uuid4().hex[:6]}",
            status="public",
            metadata_={"label": "Hauptbestand"},
        )
        db_session.add(root)
        await db_session.flush()

        # 2. Create child collection
        child = Collection(
            idno=f"COL-CHILD-{uuid.uuid4().hex[:6]}",
            parent_id=root.id,
            status="public",
            metadata_={"label": "Teilbestand A"},
        )
        db_session.add(child)
        await db_session.flush()

        # 3. Create grandchild collection
        grandchild = Collection(
            idno=f"COL-GRAND-{uuid.uuid4().hex[:6]}",
            parent_id=child.id,
            status="public",
            metadata_={"label": "Konvolut 1"},
        )
        db_session.add(grandchild)
        await db_session.flush()

        # 4. Create separate sibling collection (not under root)
        other = Collection(
            idno=f"COL-OTHER-{uuid.uuid4().hex[:6]}",
            status="public",
            metadata_={"label": "Anderer Bestand"},
        )
        db_session.add(other)
        await db_session.flush()

        # Subtree of root includes root, child, grandchild
        root_subtree = await get_collection_subtree_ids(db_session, root.id)
        assert set(root_subtree) == {root.id, child.id, grandchild.id}
        assert other.id not in root_subtree

        # Subtree of child includes child and grandchild
        child_subtree = await get_collection_subtree_ids(db_session, child.id)
        assert set(child_subtree) == {child.id, grandchild.id}

        # Subtree of grandchild is just itself
        grandchild_subtree = await get_collection_subtree_ids(db_session, grandchild.id)
        assert grandchild_subtree == [grandchild.id]


@pytest.mark.asyncio
async def test_collection_subtree_titles(app) -> None:
    async with database.AsyncSessionLocal() as db_session:
        root_title = f"Archiv Bestand {uuid.uuid4().hex[:6]}"
        child_title = f"Dokumente {uuid.uuid4().hex[:6]}"

        root = Collection(
            idno=f"IDNO-{uuid.uuid4().hex[:6]}",
            status="public",
            metadata_={"label": root_title},
        )
        db_session.add(root)
        await db_session.flush()

        child = Collection(
            idno=f"IDNO-{uuid.uuid4().hex[:6]}",
            parent_id=root.id,
            status="public",
            metadata_={"label": child_title},
        )
        db_session.add(child)
        await db_session.flush()

        # By root title
        titles = await get_collection_subtree_titles(db_session, root_title)
        assert root_title in titles
        assert child_title in titles

        # By unknown title returns [unknown]
        unknown = await get_collection_subtree_titles(db_session, "Nicht vorhanden")
        assert unknown == ["Nicht vorhanden"]


@pytest.mark.asyncio
async def test_relations_include_subcollections(async_client, auth_headers) -> None:
    # 1. Create parent collection
    parent_res = await async_client.post(
        "/v1/collections",
        headers=auth_headers,
        json={
            "idno": f"COL-{uuid.uuid4().hex[:10]}",
            "status": "public",
            "metadata_": {"label": "Parent Collection"},
        },
    )
    assert parent_res.status_code == 201, parent_res.text
    parent_id = parent_res.json()["id"]

    # 2. Create child collection
    child_res = await async_client.post(
        "/v1/collections",
        headers=auth_headers,
        json={
            "idno": f"COL-{uuid.uuid4().hex[:10]}",
            "parent_id": parent_id,
            "status": "public",
            "metadata_": {"label": "Child Collection"},
        },
    )
    assert child_res.status_code == 201, child_res.text
    child_id = child_res.json()["id"]

    # 3. Create two objects
    obj1_res = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"OBJ-{uuid.uuid4().hex[:10]}",
            "status": "public",
            "metadata_": {"label": "Objekt 1 (in Parent)"},
        },
    )
    assert obj1_res.status_code == 201, obj1_res.text
    obj1_id = obj1_res.json()["id"]

    obj2_res = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"OBJ-{uuid.uuid4().hex[:10]}",
            "status": "public",
            "metadata_": {"label": "Objekt 2 (in Child)"},
        },
    )
    assert obj2_res.status_code == 201, obj2_res.text
    obj2_id = obj2_res.json()["id"]

    # 4. Link obj1 to parent collection and obj2 to child collection
    rel1 = await async_client.post(
        "/v1/relations",
        headers=auth_headers,
        json={
            "from_type": "object",
            "from_id": obj1_id,
            "to_type": "collection",
            "to_id": parent_id,
            "relation_type": "member_of",
        },
    )
    assert rel1.status_code == 201, rel1.text

    rel2 = await async_client.post(
        "/v1/relations",
        headers=auth_headers,
        json={
            "from_type": "object",
            "from_id": obj2_id,
            "to_type": "collection",
            "to_id": child_id,
            "relation_type": "member_of",
        },
    )
    assert rel2.status_code == 201, rel2.text

    # 5. Query without include_subcollections -> only obj1
    direct_res = await async_client.get(
        f"/v1/relations?to_type=collection&to_id={parent_id}",
        headers=auth_headers,
    )
    assert direct_res.status_code == 200
    direct_items = direct_res.json()
    assert len(direct_items) == 1
    assert direct_items[0]["from_id"] == obj1_id

    # 6. Query with include_subcollections=true -> both obj1 and obj2
    sub_res = await async_client.get(
        f"/v1/relations?to_type=collection&to_id={parent_id}&include_subcollections=true",
        headers=auth_headers,
    )
    assert sub_res.status_code == 200
    sub_items = sub_res.json()
    assert len(sub_items) == 2
    from_ids = {item["from_id"] for item in sub_items}
    assert from_ids == {obj1_id, obj2_id}

    # 7. Same for portal public endpoint
    portal_res = await async_client.get(
        f"/portal/v1/relations?to_type=collection&to_id={parent_id}&include_subcollections=true"
    )
    assert portal_res.status_code == 200
    portal_from_ids = {item["from_id"] for item in portal_res.json()}
    assert portal_from_ids == {obj1_id, obj2_id}
