"""Unit tests for the cleanup_relation_refs Celery task internals."""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from katalon.workers.cleanup_tasks import _do_cleanup

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_field_def(name: str, target_type: str, record_type: str) -> MagicMock:
    fd = MagicMock()
    fd.name = name
    fd.field_type = "relation"
    fd.is_deleted = False
    fd.settings = {"target_type": target_type}
    fd.target_type = record_type
    return fd


def _make_record(metadata: dict) -> MagicMock:
    rec = MagicMock()
    rec.metadata_ = metadata
    return rec


def _make_session(field_defs: list, records: list) -> AsyncMock:
    """Build a mock session.

    execute() is called twice:
      1st call → returns field definitions (scalars().all())
      2nd call → returns records (scalars().all())
    """
    fd_result = MagicMock()
    fd_result.scalars.return_value.all.return_value = field_defs

    rec_result = MagicMock()
    rec_result.scalars.return_value.all.return_value = records

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[fd_result, rec_result])
    return session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_relation_fields_nothing_cleaned() -> None:
    session = _make_session(field_defs=[], records=[])
    result = await _do_cleanup(session, "entity", str(uuid.uuid4()))
    assert result["cleaned"] == 0
    assert result["status"] == "ok"


@pytest.mark.asyncio
async def test_no_matching_target_type_nothing_cleaned() -> None:
    # Field targets "object", but we're deleting an "entity"
    fd = _make_field_def("photographer", target_type="object", record_type="object")
    record = _make_record({"photographer": {"id": str(uuid.uuid4()), "label": "X"}})
    session = _make_session([fd], [record])
    result = await _do_cleanup(session, "entity", str(uuid.uuid4()))
    assert result["cleaned"] == 0


@pytest.mark.asyncio
async def test_scalar_relation_entry_removed() -> None:
    deleted_id = str(uuid.uuid4())
    fd = _make_field_def("creator", target_type="entity", record_type="object")
    record = _make_record({"creator": {"id": deleted_id, "label": "Gone"}})
    session = _make_session([fd], [record])

    result = await _do_cleanup(session, "entity", deleted_id)

    assert result["cleaned"] == 1
    assert record.metadata_["creator"] is None


@pytest.mark.asyncio
async def test_scalar_relation_different_id_untouched() -> None:
    deleted_id = str(uuid.uuid4())
    other_id = str(uuid.uuid4())
    fd = _make_field_def("creator", target_type="entity", record_type="object")
    record = _make_record({"creator": {"id": other_id, "label": "Still here"}})
    session = _make_session([fd], [record])

    result = await _do_cleanup(session, "entity", deleted_id)

    assert result["cleaned"] == 0
    assert record.metadata_["creator"]["id"] == other_id


@pytest.mark.asyncio
async def test_list_relation_entry_removed_from_list() -> None:
    deleted_id = str(uuid.uuid4())
    other_id = str(uuid.uuid4())
    fd = _make_field_def("photographer", target_type="entity", record_type="object")
    original = [
        {"id": deleted_id, "label": "Gone"},
        {"id": other_id, "label": "Stays"},
    ]
    record = _make_record({"photographer": list(original)})
    session = _make_session([fd], [record])

    result = await _do_cleanup(session, "entity", deleted_id)

    assert result["cleaned"] == 1
    remaining = record.metadata_["photographer"]
    assert len(remaining) == 1
    assert remaining[0]["id"] == other_id


@pytest.mark.asyncio
async def test_list_all_entries_removed_leaves_empty_list() -> None:
    deleted_id = str(uuid.uuid4())
    fd = _make_field_def("photographer", target_type="entity", record_type="object")
    record = _make_record({"photographer": [{"id": deleted_id, "label": "Gone"}]})
    session = _make_session([fd], [record])

    result = await _do_cleanup(session, "entity", deleted_id)

    assert result["cleaned"] == 1
    assert record.metadata_["photographer"] == []


@pytest.mark.asyncio
async def test_missing_field_in_metadata_skipped() -> None:
    deleted_id = str(uuid.uuid4())
    fd = _make_field_def("photographer", target_type="entity", record_type="object")
    record = _make_record({})  # field not present
    session = _make_session([fd], [record])

    result = await _do_cleanup(session, "entity", deleted_id)

    assert result["cleaned"] == 0


@pytest.mark.asyncio
async def test_multiple_records_multiple_cleaned() -> None:
    deleted_id = str(uuid.uuid4())
    fd = _make_field_def("creator", target_type="entity", record_type="object")

    records = [
        _make_record({"creator": {"id": deleted_id, "label": "Gone"}}),
        _make_record({"creator": {"id": str(uuid.uuid4()), "label": "Other"}}),
        _make_record({"creator": {"id": deleted_id, "label": "Also Gone"}}),
    ]
    session = _make_session([fd], records)

    result = await _do_cleanup(session, "entity", deleted_id)

    assert result["cleaned"] == 2


@pytest.mark.asyncio
async def test_return_metadata_contains_type_and_id() -> None:
    deleted_id = str(uuid.uuid4())
    session = _make_session([], [])
    result = await _do_cleanup(session, "place", deleted_id)
    assert result["deleted_type"] == "place"
    assert result["deleted_id"] == deleted_id
