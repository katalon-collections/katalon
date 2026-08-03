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


@pytest.mark.asyncio
async def test_validate_field_names_accepts_empty_list() -> None:
    db = AsyncMock()
    await _validate_field_names(db, "object", None, [])
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_validate_field_names_accepts_known_fields() -> None:
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = ["title", "description"]
    db.execute = AsyncMock(return_value=result)
    await _validate_field_names(db, "object", None, ["title"])


@pytest.mark.asyncio
async def test_validate_field_names_rejects_unknown_field() -> None:
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = ["title"]
    db.execute = AsyncMock(return_value=result)
    with pytest.raises(HTTPException) as exc:
        await _validate_field_names(db, "object", None, ["title", "ghost_field"])
    assert exc.value.status_code == 422
