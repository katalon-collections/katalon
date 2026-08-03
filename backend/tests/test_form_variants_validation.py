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


def _db_with_fields(rows: list[tuple[str, bool]]) -> AsyncMock:
    db = AsyncMock()
    result = MagicMock()
    result.all.return_value = rows
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.asyncio
async def test_validate_field_names_accepts_empty_list_when_no_required_fields() -> None:
    db = _db_with_fields([("title", False), ("description", False)])
    await _validate_field_names(db, "object", None, [])


@pytest.mark.asyncio
async def test_validate_field_names_accepts_known_fields() -> None:
    db = _db_with_fields([("title", False), ("description", False)])
    await _validate_field_names(db, "object", None, ["title"])


@pytest.mark.asyncio
async def test_validate_field_names_rejects_unknown_field() -> None:
    db = _db_with_fields([("title", False)])
    with pytest.raises(HTTPException) as exc:
        await _validate_field_names(db, "object", None, ["title", "ghost_field"])
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_validate_field_names_rejects_missing_required_field() -> None:
    db = _db_with_fields([("title", True), ("description", False)])
    with pytest.raises(HTTPException) as exc:
        await _validate_field_names(db, "object", None, ["description"])
    assert exc.value.status_code == 422
    assert "title" in exc.value.detail


@pytest.mark.asyncio
async def test_validate_field_names_accepts_all_required_fields_present() -> None:
    db = _db_with_fields([("title", True), ("description", False)])
    await _validate_field_names(db, "object", None, ["title", "description"])
