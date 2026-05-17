import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, call, patch

from katalon.services.relation_service import count_relations, delete_relations


def _make_db(scalar_value: int = 0) -> AsyncMock:
    count_result = MagicMock()
    count_result.scalar_one.return_value = scalar_value
    db = AsyncMock()
    db.execute = AsyncMock(return_value=count_result)
    return db


@pytest.mark.asyncio
async def test_count_relations_returns_zero() -> None:
    db = _make_db(0)
    rid = uuid.uuid4()
    count = await count_relations(db, "object", rid)
    assert count == 0
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_count_relations_returns_nonzero() -> None:
    db = _make_db(3)
    rid = uuid.uuid4()
    count = await count_relations(db, "entity", rid)
    assert count == 3


@pytest.mark.asyncio
async def test_count_relations_all_types() -> None:
    for record_type in ("object", "entity", "place", "occurrence"):
        db = _make_db(1)
        rid = uuid.uuid4()
        count = await count_relations(db, record_type, rid)
        assert count == 1, f"Failed for type {record_type}"


@pytest.mark.asyncio
async def test_delete_relations_executes_query() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock())
    rid = uuid.uuid4()
    await delete_relations(db, "object", rid)
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_relations_all_types() -> None:
    for record_type in ("object", "entity", "place", "occurrence"):
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock())
        rid = uuid.uuid4()
        await delete_relations(db, record_type, rid)
        db.execute.assert_awaited_once()
