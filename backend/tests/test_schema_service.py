import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from katalon.services.schema_service import validate_metadata


def make_field(name: str, *, is_required: bool = False, is_repeatable: bool = False, field_type: str = "text") -> MagicMock:
    f = MagicMock()
    f.name = name
    f.is_required = is_required
    f.is_repeatable = is_repeatable
    f.field_type = field_type
    f.settings = {}
    f.id = uuid.uuid4()
    return f


def make_group_field(name: str, sub_fields: list[MagicMock], *, is_required: bool = False) -> MagicMock:
    f = make_field(name, is_required=is_required, field_type="group")
    f.is_repeatable = True
    return f, sub_fields


def mock_db(*top_fields: MagicMock, sub_fields: list[MagicMock] | None = None) -> AsyncMock:
    """Mock DB that returns top_fields for the first execute call and sub_fields for subsequent calls."""
    top_result = MagicMock()
    top_result.scalars.return_value.all.return_value = list(top_fields)

    sub_result = MagicMock()
    sub_result.scalars.return_value.all.return_value = list(sub_fields or [])

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[top_result, sub_result] + [sub_result] * 10)
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


# ---------------------------------------------------------------------------
# Group / container field tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_group_field_not_a_list_is_error() -> None:
    group = make_field("foerderung", field_type="group")
    db = mock_db(group, sub_fields=[])
    errors = await validate_metadata(db, "object", {"foerderung": "not-a-list"})
    assert len(errors) == 1
    assert "Liste" in errors[0]


@pytest.mark.asyncio
async def test_group_field_required_empty_list() -> None:
    group = make_field("foerderung", field_type="group", is_required=True)
    db = mock_db(group, sub_fields=[])
    errors = await validate_metadata(db, "object", {"foerderung": []})
    assert len(errors) == 1
    assert "foerderung" in errors[0]


@pytest.mark.asyncio
async def test_group_field_required_sub_field_missing() -> None:
    group = make_field("foerderung", field_type="group")
    nummer = make_field("nummer", is_required=True)
    db = mock_db(group, sub_fields=[nummer])
    errors = await validate_metadata(db, "object", {"foerderung": [{"nummer": ""}]})
    assert len(errors) == 1
    assert "foerderung.nummer" in errors[0]
    assert "Eintrag 1" in errors[0]


@pytest.mark.asyncio
async def test_group_field_valid_instances() -> None:
    group = make_field("foerderung", field_type="group")
    nummer = make_field("nummer", is_required=True)
    db = mock_db(group, sub_fields=[nummer])
    errors = await validate_metadata(db, "object", {
        "foerderung": [
            {"nummer": "FU-2023-001"},
            {"nummer": "FU-2024-042"},
        ]
    })
    assert errors == []


@pytest.mark.asyncio
async def test_group_field_sub_field_regex_violation() -> None:
    group = make_field("foerderung", field_type="group")
    url = make_field("url")
    url.settings = {"validation_regex": r"^https?://.+"}
    db = mock_db(group, sub_fields=[url])
    errors = await validate_metadata(db, "object", {"foerderung": [{"url": "not-a-url"}]})
    assert len(errors) == 1
    assert "foerderung.url" in errors[0]


@pytest.mark.asyncio
async def test_group_field_optional_absent() -> None:
    group = make_field("foerderung", field_type="group")
    db = mock_db(group, sub_fields=[])
    errors = await validate_metadata(db, "object", {})
    assert errors == []
