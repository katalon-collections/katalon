from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from katalon.services.subtype_service import (
    ensure_subtype_exists,
    normalize_subtype_name,
    subtype_has_assigned_records,
)


def _result(*, one_or_none=None, one=0) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = one_or_none
    result.scalar_one.return_value = one
    return result


@pytest.mark.asyncio
async def test_ensure_subtype_exists_accepts_existing_value() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_result(one_or_none=object()))
    await ensure_subtype_exists(db, "object", "photograph")


@pytest.mark.asyncio
async def test_ensure_subtype_exists_rejects_unknown_value() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_result(one_or_none=None))

    with pytest.raises(HTTPException) as exc:
        await ensure_subtype_exists(db, "object", "unknown")

    assert exc.value.status_code == 422


def test_normalize_subtype_name_allows_null_when_configured() -> None:
    assert normalize_subtype_name(None, allow_null=True) is None
    assert normalize_subtype_name("  ", allow_null=True) is None
    assert normalize_subtype_name(" photo ", allow_null=True) == "photo"


def test_normalize_subtype_name_requires_value_when_not_nullable() -> None:
    with pytest.raises(HTTPException):
        normalize_subtype_name(None, allow_null=False)
    with pytest.raises(HTTPException):
        normalize_subtype_name(" ", allow_null=False)


@pytest.mark.asyncio
async def test_subtype_has_assigned_records_true_when_count_positive() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_result(one=2))
    assert await subtype_has_assigned_records(db, "object", "photograph") is True


@pytest.mark.asyncio
async def test_subtype_has_assigned_records_false_when_count_zero() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_result(one=0))
    assert await subtype_has_assigned_records(db, "object", "photograph") is False
