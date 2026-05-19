"""Tests for the 409 Conflict response on delete when relations exist."""
import pytest
from httpx import ASGITransport, AsyncClient

from katalon.main import app

# ---------------------------------------------------------------------------
# Auth-required tests (no DB needed — rejected before handler logic runs)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_object_requires_auth() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.delete("/v1/objects/00000000-0000-0000-0000-000000000001")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_delete_entity_requires_auth() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.delete("/v1/entities/00000000-0000-0000-0000-000000000001")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_delete_place_requires_auth() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.delete("/v1/places/00000000-0000-0000-0000-000000000001")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_delete_occurrence_requires_auth() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.delete("/v1/occurrences/00000000-0000-0000-0000-000000000001")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# force=true query param — accessible without auth check confirming it's wired
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_object_with_force_param_still_requires_auth() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.delete("/v1/objects/00000000-0000-0000-0000-000000000001?force=true")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_delete_entity_with_force_param_still_requires_auth() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.delete("/v1/entities/00000000-0000-0000-0000-000000000001?force=true")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# 409 response shape test via dependency overrides
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_object_returns_409_when_relations_exist() -> None:
    """Override DB and auth dependencies to simulate a record with relations."""
    import uuid
    from unittest.mock import AsyncMock, MagicMock

    from katalon.core.dependencies import get_current_user, get_db

    record_id = uuid.uuid4()
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()

    # The handler calls db.execute() multiple times:
    # 1. select(Object).where(...) → find the record
    # 2. count_relations → scalar_one() returns 2
    obj_mock = MagicMock()
    obj_mock.id = record_id
    obj_mock.idno = "OBJ-001"

    find_result = MagicMock()
    find_result.scalar_one_or_none.return_value = obj_mock

    count_result = MagicMock()
    count_result.scalar_one.return_value = 2

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[find_result, count_result])
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)

    async def override_db():
        yield mock_db

    async def override_user():
        return mock_user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.delete(f"/v1/objects/{record_id}")
        assert r.status_code == 409
        body = r.json()
        assert "related_count" in body["detail"]
        assert body["detail"]["related_count"] == 2
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_entity_returns_409_when_relations_exist() -> None:
    """Same pattern for entities."""
    import uuid
    from unittest.mock import AsyncMock, MagicMock

    from katalon.core.dependencies import get_current_user, get_db

    record_id = uuid.uuid4()
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()

    entity_mock = MagicMock()
    entity_mock.id = record_id

    find_result = MagicMock()
    find_result.scalar_one_or_none.return_value = entity_mock

    count_result = MagicMock()
    count_result.scalar_one.return_value = 5

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[find_result, count_result])

    async def override_db():
        yield mock_db

    async def override_user():
        return mock_user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.delete(f"/v1/entities/{record_id}")
        assert r.status_code == 409
        body = r.json()
        assert body["detail"]["related_count"] == 5
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_object_409_detail_message_contains_count() -> None:
    """The detail message should include the count."""
    import uuid
    from unittest.mock import AsyncMock, MagicMock

    from katalon.core.dependencies import get_current_user, get_db

    record_id = uuid.uuid4()
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()

    obj_mock = MagicMock()
    obj_mock.id = record_id

    find_result = MagicMock()
    find_result.scalar_one_or_none.return_value = obj_mock

    count_result = MagicMock()
    count_result.scalar_one.return_value = 7

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=[find_result, count_result])

    async def override_db():
        yield mock_db

    async def override_user():
        return mock_user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.delete(f"/v1/objects/{record_id}")
        assert r.status_code == 409
        body = r.json()
        assert "7" in body["detail"]["detail"]
    finally:
        app.dependency_overrides.clear()
