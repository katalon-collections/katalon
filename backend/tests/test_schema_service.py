import pytest
from unittest.mock import AsyncMock, MagicMock

from katalon.services.schema_service import validate_metadata


def make_field(name: str, *, is_required: bool = False, is_repeatable: bool = False) -> MagicMock:
    f = MagicMock()
    f.name = name
    f.is_required = is_required
    f.is_repeatable = is_repeatable
    return f


def mock_db(*fields: MagicMock) -> AsyncMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = list(fields)
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.asyncio
async def test_no_fields_no_errors() -> None:
    db = mock_db()
    errors = await validate_metadata(db, "object", {})
    assert errors == []


@pytest.mark.asyncio
async def test_required_field_missing() -> None:
    db = mock_db(make_field("title", is_required=True))
    errors = await validate_metadata(db, "object", {})
    assert len(errors) == 1
    assert "title" in errors[0]


@pytest.mark.asyncio
async def test_required_field_empty_string() -> None:
    db = mock_db(make_field("title", is_required=True))
    errors = await validate_metadata(db, "object", {"title": ""})
    assert len(errors) == 1


@pytest.mark.asyncio
async def test_required_field_empty_list() -> None:
    db = mock_db(make_field("tags", is_required=True, is_repeatable=True))
    errors = await validate_metadata(db, "object", {"tags": []})
    assert len(errors) == 1


@pytest.mark.asyncio
async def test_required_field_present_no_error() -> None:
    db = mock_db(make_field("title", is_required=True))
    errors = await validate_metadata(db, "object", {"title": "Bahnhofstraße"})
    assert errors == []


@pytest.mark.asyncio
async def test_repeatable_not_list_is_error() -> None:
    db = mock_db(make_field("tags", is_repeatable=True))
    errors = await validate_metadata(db, "object", {"tags": "einzelner-wert"})
    assert len(errors) == 1
    assert "Liste" in errors[0]


@pytest.mark.asyncio
async def test_repeatable_list_ok() -> None:
    db = mock_db(make_field("tags", is_repeatable=True))
    errors = await validate_metadata(db, "object", {"tags": ["a", "b"]})
    assert errors == []


@pytest.mark.asyncio
async def test_non_repeatable_list_is_error() -> None:
    db = mock_db(make_field("title", is_repeatable=False))
    errors = await validate_metadata(db, "object", {"title": ["a", "b"]})
    assert len(errors) == 1


@pytest.mark.asyncio
async def test_optional_field_absent_no_error() -> None:
    db = mock_db(make_field("description", is_required=False))
    errors = await validate_metadata(db, "object", {})
    assert errors == []


@pytest.mark.asyncio
async def test_multiple_fields_multiple_errors() -> None:
    db = mock_db(
        make_field("title", is_required=True),
        make_field("rights", is_required=True),
    )
    errors = await validate_metadata(db, "object", {})
    assert len(errors) == 2


@pytest.mark.asyncio
async def test_valid_complex_metadata() -> None:
    db = mock_db(
        make_field("title", is_required=True),
        make_field("tags", is_repeatable=True),
        make_field("description"),
    )
    errors = await validate_metadata(db, "object", {
        "title": "Bahnhofstraße bei Nacht",
        "tags": ["zürich", "nacht", "strasse"],
    })
    assert errors == []
