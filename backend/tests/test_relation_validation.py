"""Unit tests for relation field type validation in schema_service."""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from katalon.api.v1.schema_admin import _validate_field_settings
from katalon.core.schemas import FieldDefinitionCreate
from katalon.services.schema_service import (
    _validate_fixed_relation_type,
    _validate_relation_structure,
    _validate_relation_target,
    validate_metadata,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_relation_field(
    name: str,
    *,
    is_required: bool = False,
    is_repeatable: bool = False,
    settings: dict | None = None,
) -> MagicMock:
    f = MagicMock()
    f.name = name
    f.field_type = "relation"
    f.is_required = is_required
    f.is_repeatable = is_repeatable
    f.settings = settings or {}
    return f


def mock_db_fields(*fields: MagicMock, extra_execute_results: list | None = None) -> AsyncMock:
    """Returns a DB mock whose first execute() returns the given fields,
    and subsequent calls return items from extra_execute_results (for target lookups)."""
    field_result = MagicMock()
    field_result.scalars.return_value.all.return_value = list(fields)

    side_effects = [field_result]
    if extra_execute_results:
        side_effects.extend(extra_execute_results)

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=side_effects)
    return db


def _found_result() -> MagicMock:
    """Simulates a DB result where the record exists."""
    r = MagicMock()
    r.scalar_one_or_none.return_value = MagicMock()
    return r


def _not_found_result() -> MagicMock:
    """Simulates a DB result where the record does not exist."""
    r = MagicMock()
    r.scalar_one_or_none.return_value = None
    return r


# ---------------------------------------------------------------------------
# _validate_relation_structure
# ---------------------------------------------------------------------------


def test_structure_valid_entry() -> None:
    entry = {"id": str(uuid.uuid4()), "label": "Max Mustermann", "relation_type": "Auftraggeber"}
    assert _validate_relation_structure(entry, "photographer") is None


def test_structure_not_a_dict() -> None:
    err = _validate_relation_structure("just-a-string", "photographer")
    assert err is not None
    assert "photographer" in err


def test_structure_missing_id() -> None:
    err = _validate_relation_structure({"label": "Someone"}, "photographer")
    assert err is not None
    assert "id" in err


def test_structure_invalid_uuid() -> None:
    err = _validate_relation_structure({"id": "not-a-uuid", "label": "X"}, "photographer")
    assert err is not None
    assert "not-a-uuid" in err


def test_structure_missing_label() -> None:
    err = _validate_relation_structure({"id": str(uuid.uuid4()), "label": ""}, "photographer")
    assert err is not None
    assert "label" in err


def test_structure_label_none() -> None:
    err = _validate_relation_structure({"id": str(uuid.uuid4())}, "photographer")
    assert err is not None
    assert "label" in err


def test_fixed_relation_type_rejects_other_type() -> None:
    entry = {"id": str(uuid.uuid4()), "label": "Max", "relation_type": "publisher"}
    assert _validate_fixed_relation_type(entry, "author", {"fixed_relation_type": "has_author"})


@pytest.mark.asyncio
async def test_relation_field_rejects_vocab_without_matching_type_pair() -> None:
    db = AsyncMock()
    db.get = AsyncMock(return_value=MagicMock(kind="relation", id=uuid.uuid4()))
    db.scalar = AsyncMock(return_value=None)
    field = FieldDefinitionCreate(
        target_type="object",
        name="author",
        label={"de": "Autor:in"},
        field_type="relation",
        settings={"target_type": "entity", "relation_type_vocab": str(uuid.uuid4())},
    )

    with pytest.raises(HTTPException, match="keinen Typ"):
        await _validate_field_settings(db, field)


# ---------------------------------------------------------------------------
# _validate_relation_target
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_relation_field_requires_relation_type_vocabulary() -> None:
    field = FieldDefinitionCreate(
        target_type="object",
        name="author",
        label={"de": "Autor:in"},
        field_type="relation",
        settings={"target_type": "entity"},
    )

    with pytest.raises(HTTPException, match="benötigt ein Relationstyp-Vokabular"):
        await _validate_field_settings(AsyncMock(), field)


@pytest.mark.asyncio
async def test_target_no_target_type_setting_skips_db() -> None:
    db = AsyncMock()
    entry = {"id": str(uuid.uuid4()), "label": "X"}
    err = await _validate_relation_target(entry, "photographer", {}, db)
    assert err is None
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_target_unknown_target_type_skips_db() -> None:
    db = AsyncMock()
    entry = {"id": str(uuid.uuid4()), "label": "X"}
    err = await _validate_relation_target(entry, "photographer", {"target_type": "foobar"}, db)
    assert err is None
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_target_record_found_no_error() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_found_result())
    entry = {"id": str(uuid.uuid4()), "label": "Max Mustermann"}
    err = await _validate_relation_target(entry, "photographer", {"target_type": "entity"}, db)
    assert err is None


@pytest.mark.asyncio
async def test_target_record_not_found_returns_error() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_not_found_result())
    record_id = str(uuid.uuid4())
    entry = {"id": record_id, "label": "Gone"}
    err = await _validate_relation_target(entry, "photographer", {"target_type": "entity"}, db)
    assert err is not None
    assert record_id in err
    assert "entity" in err


@pytest.mark.asyncio
async def test_target_all_primary_types_accepted() -> None:
    for target_type in ("object", "entity", "place", "occurrence", "procedure"):
        db = AsyncMock()
        db.execute = AsyncMock(return_value=_found_result())
        entry = {"id": str(uuid.uuid4()), "label": "Test"}
        err = await _validate_relation_target(entry, "rel_field", {"target_type": target_type}, db)
        assert err is None, f"Unexpected error for target_type={target_type}: {err}"


# ---------------------------------------------------------------------------
# validate_metadata integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_relation_field_valid_single() -> None:
    field = make_relation_field("photographer", settings={"target_type": "entity"})
    entry = {"id": str(uuid.uuid4()), "label": "Max Mustermann", "relation_type": "Auftraggeber"}
    db = mock_db_fields(field, extra_execute_results=[_found_result()])
    errors = await validate_metadata(db, "object", {"photographer": entry})
    assert errors == []


@pytest.mark.asyncio
async def test_relation_field_valid_repeatable() -> None:
    field = make_relation_field(
        "photographer",
        is_repeatable=True,
        settings={"target_type": "entity"},
    )
    entries = [
        {"id": str(uuid.uuid4()), "label": "Alice", "relation_type": "Fotografin"},
        {"id": str(uuid.uuid4()), "label": "Bob", "relation_type": "Auftraggeber"},
    ]
    db = mock_db_fields(field, extra_execute_results=[_found_result(), _found_result()])
    errors = await validate_metadata(db, "object", {"photographer": entries})
    assert errors == []


@pytest.mark.asyncio
async def test_relation_field_invalid_structure_in_list() -> None:
    field = make_relation_field("photographer", is_repeatable=True)
    db = mock_db_fields(field)
    errors = await validate_metadata(db, "object", {"photographer": ["not-a-dict"]})
    assert len(errors) == 1
    assert "photographer" in errors[0]


@pytest.mark.asyncio
async def test_relation_field_not_list_when_repeatable() -> None:
    field = make_relation_field("photographer", is_repeatable=True)
    entry = {"id": str(uuid.uuid4()), "label": "Max"}
    db = mock_db_fields(field)
    errors = await validate_metadata(db, "object", {"photographer": entry})
    assert len(errors) == 1
    assert "Liste" in errors[0]


@pytest.mark.asyncio
async def test_relation_field_target_not_found_returns_error() -> None:
    field = make_relation_field("photographer", settings={"target_type": "entity"})
    entry = {"id": str(uuid.uuid4()), "label": "Gone"}
    db = mock_db_fields(field, extra_execute_results=[_not_found_result()])
    errors = await validate_metadata(db, "object", {"photographer": entry})
    assert len(errors) == 1
    assert "entity" in errors[0]


@pytest.mark.asyncio
async def test_relation_field_required_missing() -> None:
    field = make_relation_field("photographer", is_required=True)
    db = mock_db_fields(field)
    errors = await validate_metadata(db, "object", {})
    assert len(errors) == 1
    assert "photographer" in errors[0]


@pytest.mark.asyncio
async def test_relation_field_absent_optional_no_error() -> None:
    field = make_relation_field("photographer", is_required=False)
    db = mock_db_fields(field)
    errors = await validate_metadata(db, "object", {})
    assert errors == []
