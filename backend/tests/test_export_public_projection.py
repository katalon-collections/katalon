# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""CSV/JSON dumps for callers without read permission use the public projection."""

import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from katalon.services import export_service


def _field(name: str, *, is_public: bool, field_type: str = "text") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        name=name,
        field_type=field_type,
        is_public=is_public,
        parent_id=None,
        target_subtype=None,
        is_repeatable=False,
        settings={},
    )


@pytest.mark.parametrize("record_type", ["procedure", "storage_location"])
async def test_internal_types_export_nothing_without_read_permission(record_type: str) -> None:
    records, fields = await export_service._load_records(None, record_type, None, None)  # type: ignore[arg-type]
    assert records == [] and fields == []


async def test_public_dump_drops_internal_and_file_fields(monkeypatch) -> None:
    public = _field("titel", is_public=True)
    attachment = _field("anhang", is_public=True, field_type="file")

    async def load_public_fields(_db, _record_type):
        return [public, attachment]

    async def no_hidden(_db, _metadatas, _fields):
        return set()

    record = SimpleNamespace(
        id=uuid.uuid4(),
        idno="OBJ-1",
        object_type="foto",
        status="public",
        metadata_={
            "titel": "Öffentlich",
            "intern": "Geheim",
            "anhang": {"id": str(uuid.uuid4()), "filename": "vertrag.pdf"},
        },
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    async def load_records(*_args):
        return [record], [public]

    monkeypatch.setattr(export_service, "load_public_fields", load_public_fields)
    monkeypatch.setattr(export_service, "load_hidden_relation_targets", no_hidden)
    monkeypatch.setattr(export_service, "_load_records", load_records)

    dumped = json.loads(
        "".join([c async for c in export_service.stream_json(None, "object", None, None)])
    )
    csv_dump = "".join([c async for c in export_service.stream_csv(None, "object", None, None)])

    assert dumped[0]["metadata"] == {"titel": "Öffentlich"}
    assert "Geheim" not in csv_dump and "vertrag.pdf" not in csv_dump
    assert "intern" not in csv_dump.splitlines()[0]
    # The ORM object is never mutated (would be flushed back to the database).
    assert record.metadata_["intern"] == "Geheim"
