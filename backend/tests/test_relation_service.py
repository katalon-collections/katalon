# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from katalon.core.models import FieldDefinition, VocabularyTerm
from katalon.services.relation_service import (
    count_relations,
    delete_relations,
    sync_schema_relations,
    validate_relation_endpoint,
)
from katalon.services.relation_type_service import validate_relation_type_applicability


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
    for record_type in ("object", "entity", "place", "occurrence", "procedure"):
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
    for record_type in ("object", "entity", "place", "occurrence", "procedure"):
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock())
        rid = uuid.uuid4()
        await delete_relations(db, record_type, rid)
        db.execute.assert_awaited_once()


def _make_terms_db(terms: list[VocabularyTerm]) -> AsyncMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = terms
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.asyncio
async def test_validate_relation_type_no_term_is_unrestricted() -> None:
    db = _make_terms_db([])
    error = await validate_relation_type_applicability(db, "object", "place", "depicts")
    assert error is None


@pytest.mark.asyncio
async def test_validate_relation_type_allows_matching_pair() -> None:
    term = VocabularyTerm(applies_from=["object"], applies_to=["entity"])
    db = _make_terms_db([term])
    error = await validate_relation_type_applicability(db, "object", "entity", "published_by")
    assert error is None


@pytest.mark.asyncio
async def test_validate_relation_type_rejects_wrong_pair() -> None:
    term = VocabularyTerm(applies_from=["object"], applies_to=["entity"])
    db = _make_terms_db([term])
    error = await validate_relation_type_applicability(db, "object", "place", "published_by")
    assert error is not None
    assert "published_by" in error

@pytest.mark.asyncio
async def test_validate_relation_endpoint_unknown_type() -> None:
    db = AsyncMock()
    err = await validate_relation_endpoint(db, "unknown_type", uuid.uuid4())
    assert err is not None
    assert "Ungültiger Datensatztyp" in err


@pytest.mark.asyncio
async def test_validate_relation_endpoint_not_found() -> None:
    db = AsyncMock()
    exec_mock = MagicMock()
    exec_mock.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=exec_mock)
    err = await validate_relation_endpoint(db, "object", uuid.uuid4())
    assert err is not None
    assert "existiert nicht oder ist gelöscht" in err


@pytest.mark.asyncio
async def test_validate_relation_endpoint_found() -> None:
    db = AsyncMock()
    target_id = uuid.uuid4()
    exec_mock = MagicMock()
    exec_mock.scalar_one_or_none.return_value = target_id
    db.execute = AsyncMock(return_value=exec_mock)
    err = await validate_relation_endpoint(db, "object", target_id)
    assert err is None


@pytest.mark.asyncio
async def test_sync_schema_relations_filters_unresolvable_targets() -> None:
    field = FieldDefinition(
        name="creator",
        target_type="object",
        field_type="relation",
        is_repeatable=False,
        settings={"target_type": "entity"},
        is_deleted=False,
    )
    rel_res = MagicMock()
    rel_res.scalars.return_value.all.return_value = [field]

    group_res = MagicMock()
    group_res.scalars.return_value.all.return_value = []

    manual_res = MagicMock()
    manual_res.all.return_value = []

    # Target entity check returns None (not found)
    target_res = MagicMock()
    target_res.scalar_one_or_none.return_value = None

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[rel_res, group_res, MagicMock(), manual_res, target_res])

    missing_target_id = uuid.uuid4()
    metadata = {"creator": {"id": str(missing_target_id), "relation_type": "created_by"}}

    await sync_schema_relations(db, "object", uuid.uuid4(), metadata)

    # Ensure db.add was NOT called because target did not resolve
    db.add.assert_not_called()
