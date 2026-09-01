# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from katalon.api.v1.form_variants import _validate_field_names, _validate_target_type


def test_validate_target_type_accepts_known_primary_type() -> None:
    _validate_target_type("object")


def test_validate_target_type_rejects_vocabulary_term() -> None:
    with pytest.raises(HTTPException) as exc:
        _validate_target_type("vocabulary_term")
    assert exc.value.status_code == 422


def test_validate_target_type_rejects_unknown_type() -> None:
    with pytest.raises(HTTPException) as exc:
        _validate_target_type("nonsense")
    assert exc.value.status_code == 422


def _db_with_fields(
    rows: list[tuple[uuid.UUID, str, str, bool]],
    required_child_parent_ids: list[uuid.UUID] | None = None,
) -> AsyncMock:
    db = AsyncMock()
    field_result = MagicMock()
    field_result.all.return_value = rows
    child_result = MagicMock()
    child_result.scalars.return_value.all.return_value = required_child_parent_ids or []
    db.execute = AsyncMock(side_effect=[field_result, child_result])
    return db


@pytest.mark.asyncio
async def test_validate_field_names_accepts_empty_list_when_no_required_fields() -> None:
    db = _db_with_fields(
        [(uuid.uuid4(), "title", "text", False), (uuid.uuid4(), "description", "text", False)]
    )
    await _validate_field_names(db, "object", None, [])


@pytest.mark.asyncio
async def test_validate_field_names_accepts_known_fields() -> None:
    db = _db_with_fields(
        [(uuid.uuid4(), "title", "text", False), (uuid.uuid4(), "description", "text", False)]
    )
    await _validate_field_names(db, "object", None, ["title"])


@pytest.mark.asyncio
async def test_validate_field_names_rejects_unknown_field() -> None:
    db = _db_with_fields([(uuid.uuid4(), "title", "text", False)])
    with pytest.raises(HTTPException) as exc:
        await _validate_field_names(db, "object", None, ["title", "ghost_field"])
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_validate_field_names_rejects_missing_required_field() -> None:
    db = _db_with_fields(
        [(uuid.uuid4(), "title", "text", True), (uuid.uuid4(), "description", "text", False)]
    )
    with pytest.raises(HTTPException) as exc:
        await _validate_field_names(db, "object", None, ["description"])
    assert exc.value.status_code == 422
    assert "title" in exc.value.detail


@pytest.mark.asyncio
async def test_validate_field_names_accepts_all_required_fields_present() -> None:
    db = _db_with_fields(
        [(uuid.uuid4(), "title", "text", True), (uuid.uuid4(), "description", "text", False)]
    )
    await _validate_field_names(db, "object", None, ["title", "description"])


@pytest.mark.asyncio
async def test_validate_field_names_rejects_missing_group_with_required_child() -> None:
    group_id = uuid.uuid4()
    db = _db_with_fields([(group_id, "provenance", "group", False)], [group_id])

    with pytest.raises(HTTPException) as exc:
        await _validate_field_names(db, "object", None, [])

    assert exc.value.status_code == 422
    assert "provenance" in exc.value.detail


@pytest.mark.asyncio
async def test_validate_field_names_accepts_group_with_required_child() -> None:
    group_id = uuid.uuid4()
    db = _db_with_fields([(group_id, "provenance", "group", False)], [group_id])

    await _validate_field_names(db, "object", None, ["provenance"])


@pytest.mark.asyncio
async def test_validate_field_names_allows_missing_group_with_optional_children() -> None:
    group_id = uuid.uuid4()
    db = _db_with_fields([(group_id, "provenance", "group", False)])

    await _validate_field_names(db, "object", None, [])


@pytest.mark.asyncio
async def test_validate_field_names_ignores_deleted_required_children() -> None:
    group_id = uuid.uuid4()
    db = _db_with_fields([(group_id, "provenance", "group", False)])

    await _validate_field_names(db, "object", None, [])

    child_query = db.execute.call_args_list[1].args[0]
    assert "field_definitions.is_deleted IS false" in str(child_query)
