# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from katalon.core.dependencies import get_db
from katalon.core.models import Collection
from katalon.main import app


@pytest.mark.asyncio
async def test_portal_list_collections() -> None:
    session = AsyncMock()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 1

    now = datetime.now(UTC)
    col = Collection(
        id=uuid.uuid4(),
        idno="COLL-001",
        status="published",
        collection_type="holding",
        metadata_={"title": "Sammlung Müller"},
        created_at=now,
        updated_at=now,
    )
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [col]
    items_result = MagicMock()
    items_result.scalars.return_value = scalars_mock

    pub_fields_res = MagicMock()
    pub_fields_scalars = MagicMock()
    pub_fields_scalars.all.return_value = []
    pub_fields_res.scalars.return_value = pub_fields_scalars
    session.execute.side_effect = [count_result, items_result, pub_fields_res]

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/portal/v1/collections")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["idno"] == "COLL-001"


@pytest.mark.asyncio
async def test_portal_get_collection_with_hierarchy_and_members() -> None:
    parent_id = uuid.uuid4()
    col_id = uuid.uuid4()
    child_id = uuid.uuid4()
    now = datetime.now(UTC)
    col = Collection(
        id=col_id,
        idno="COLL-002",
        status="published",
        parent_id=parent_id,
        metadata_={"title": "Teilnachlass"},
        created_at=now,
        updated_at=now,
    )
    parent_col = Collection(
        id=parent_id,
        idno="COLL-001",
        status="published",
        parent_id=None,
        metadata_={"title": "Gesamtnachlass"},
        created_at=now,
        updated_at=now,
    )
    child_col = Collection(
        id=child_id,
        idno="COLL-003",
        status="published",
        parent_id=col_id,
        metadata_={"title": "Serie 1"},
        created_at=now,
        updated_at=now,
    )

    session = AsyncMock()

    # 1. get col
    res1 = MagicMock()
    res1.scalar_one_or_none.return_value = col

    # 2. ancestor parent_col
    res2 = MagicMock()
    res2.scalar_one_or_none.return_value = parent_col

    # 3. children
    res3 = MagicMock()
    scalars3 = MagicMock()
    scalars3.all.return_value = [child_col]
    res3.scalars.return_value = scalars3

    # 4. member objects count
    res4 = MagicMock()
    res4.scalar_one.return_value = 5

    # load_public_fields result
    pub_fields_res = MagicMock()
    pub_fields_scalars = MagicMock()
    pub_fields_scalars.all.return_value = []
    pub_fields_res.scalars.return_value = pub_fields_scalars

    # res1: col, res_pub: load_public_fields, res2: parent_col, res2_stop: None, res3: children, res4: count
    res_ancestor_stop = MagicMock()
    res_ancestor_stop.scalar_one_or_none.return_value = None
    # parent_col has parent_id=None, so loop stops immediately after res2! No res_ancestor_stop needed.
    session.execute.side_effect = [res1, pub_fields_res, res2, res3, res4]

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/portal/v1/collections/{col_id}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(col_id)
    assert data["parent"]["id"] == str(parent_id)
    assert len(data["ancestors"]) == 1
    assert data["ancestors"][0]["title"] == "Gesamtnachlass"
    assert len(data["children"]) == 1
    assert data["children"][0]["title"] == "Serie 1"
    assert data["member_objects_count"] == 5
