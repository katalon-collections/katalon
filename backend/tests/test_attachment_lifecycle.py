# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Attachment trust boundary on save, hard delete and the attachments-gc command."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from katalon.core.media_storage import StorageDeleteError
from katalon.core.models import Attachment, FieldDefinition
from katalon.services import attachment_service, schema_service
from katalon.services.attachment_service import (
    gc_attachments,
    parse_older_than,
    purge_record_attachments,
)


def _field(name: str, field_type: str = "file", *, repeatable=False, parent=None) -> FieldDefinition:
    return FieldDefinition(
        id=uuid.uuid4(),
        target_type="object",
        name=name,
        label={},
        field_type=field_type,
        is_required=False,
        is_repeatable=repeatable,
        is_translatable=False,
        settings={},
        parent_id=parent.id if parent is not None else None,
    )


def _attachment(record_id: uuid.UUID, *, created_at: datetime | None = None) -> Attachment:
    return Attachment(
        id=uuid.uuid4(),
        record_type="object",
        record_id=record_id,
        filename="echt.pdf",
        mime_type="application/pdf",
        size=123,
        storage_key=f"attachments/x/{uuid.uuid4()}--echt.pdf",
        created_at=created_at or datetime.now(UTC).replace(tzinfo=None),
    )


def _rows_db(*rows_per_call) -> AsyncMock:
    """Session whose successive execute() calls return the given row lists via scalars().all()."""
    db = AsyncMock()
    results = []
    for rows in rows_per_call:
        result = MagicMock()
        result.scalars.return_value.all.return_value = list(rows)
        results.append(result)
    db.execute = AsyncMock(side_effect=results)
    return db


def _use_fields(monkeypatch, top: list, subs: dict | None = None) -> None:
    async def fields(db, record_type, target_subtype=None):
        return top

    async def sub_fields(db, parent_id):
        return (subs or {}).get(parent_id, [])

    monkeypatch.setattr(schema_service, "get_field_definitions", fields)
    monkeypatch.setattr(schema_service, "get_sub_field_definitions", sub_fields)


# --- save: trust boundary -------------------------------------------------------------


@pytest.mark.asyncio
async def test_foreign_attachment_id_is_rejected(monkeypatch) -> None:
    _use_fields(monkeypatch, [_field("vertrag")])
    foreign = str(uuid.uuid4())
    db = _rows_db([])  # no row with this id belongs to (object, record)
    errors = await schema_service.validate_metadata(
        db, "object", {"vertrag": {"id": foreign, "filename": "x.pdf"}}, record_id=uuid.uuid4()
    )
    assert errors == ["Feld 'vertrag': Datei gehört nicht zu diesem Datensatz."]


@pytest.mark.asyncio
async def test_own_attachment_is_normalized_from_table(monkeypatch) -> None:
    _use_fields(monkeypatch, [_field("vertrag", repeatable=True)])
    record_id = uuid.uuid4()
    row = _attachment(record_id)
    client_value = {
        "id": str(row.id).upper(),  # client case must not matter
        "filename": "fake.html",
        "mime_type": "text/html",
        "size": 1,
        "extra": "injected",
    }
    metadata = {"vertrag": [client_value]}
    db = _rows_db([row])

    errors = await schema_service.validate_metadata(
        db, "object", metadata, record_id=record_id
    )

    assert errors == []
    assert metadata["vertrag"] == [
        {
            "id": str(row.id),
            "filename": "echt.pdf",
            "mime_type": "application/pdf",
            "size": 123,
        }
    ]


@pytest.mark.asyncio
async def test_file_reference_without_record_id_is_rejected(monkeypatch) -> None:
    _use_fields(monkeypatch, [_field("vertrag")])
    db = AsyncMock()
    errors = await schema_service.validate_metadata(
        db, "object", {"vertrag": {"id": str(uuid.uuid4())}}
    )
    assert errors == [
        "Feld 'vertrag': Dateien können erst nach dem Speichern des Datensatzes hochgeladen werden."
    ]
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_group_subfield_reference_is_checked_and_normalized(monkeypatch) -> None:
    group = _field("fan", "group", repeatable=True)
    sub = _field("datei", "file", parent=group)
    _use_fields(monkeypatch, [group], {group.id: [sub]})
    record_id = uuid.uuid4()
    row = _attachment(record_id)

    foreign_metadata = {"fan": [{"titel": "a", "datei": {"id": str(uuid.uuid4())}}]}
    errors = await schema_service.validate_metadata(
        _rows_db([]), "object", foreign_metadata, record_id=record_id
    )
    assert errors == ["Feld 'fan.datei (Eintrag 1)': Datei gehört nicht zu diesem Datensatz."]

    own_metadata = {"fan": [{"titel": "a", "datei": {"id": str(row.id), "filename": "x"}}]}
    errors = await schema_service.validate_metadata(
        _rows_db([row]), "object", own_metadata, record_id=record_id
    )
    assert errors == []
    assert own_metadata["fan"][0]["datei"] == {
        "id": str(row.id),
        "filename": "echt.pdf",
        "mime_type": "application/pdf",
        "size": 123,
    }
    assert own_metadata["fan"][0]["titel"] == "a"


@pytest.mark.asyncio
async def test_references_without_record_id_are_rejected_in_group(monkeypatch) -> None:
    group = _field("fan", "group", repeatable=True)
    sub = _field("datei", "file", parent=group)
    _use_fields(monkeypatch, [group], {group.id: [sub]})
    errors = await schema_service.validate_metadata(
        AsyncMock(), "object", {"fan": [{"datei": {"id": str(uuid.uuid4())}}]}
    )
    assert errors == [
        "Feld 'fan.datei (Eintrag 1)': Dateien können erst nach dem Speichern des Datensatzes hochgeladen werden."
    ]


@pytest.mark.asyncio
async def test_metadata_without_file_refs_does_not_query(monkeypatch) -> None:
    _use_fields(monkeypatch, [_field("vertrag")])
    db = AsyncMock()
    assert await schema_service.validate_metadata(db, "object", {}) == []
    db.execute.assert_not_called()


# --- hard delete -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_purge_deletes_rows_and_storage_keys(monkeypatch) -> None:
    record_id = uuid.uuid4()
    rows = [_attachment(record_id), _attachment(record_id)]
    db = _rows_db(rows)
    storage = MagicMock()
    storage.delete = AsyncMock()
    monkeypatch.setattr(attachment_service, "get_storage", lambda: storage)

    await purge_record_attachments(db, "object", record_id)

    storage.delete.assert_awaited_once_with(*[r.storage_key for r in rows])
    assert [c.args[0] for c in db.delete.await_args_list] == rows


@pytest.mark.asyncio
async def test_purge_storage_failure_does_not_block_row_deletion(monkeypatch) -> None:
    record_id = uuid.uuid4()
    rows = [_attachment(record_id)]
    db = _rows_db(rows)
    storage = MagicMock()
    storage.delete = AsyncMock(side_effect=StorageDeleteError({rows[0].storage_key: "denied"}))
    monkeypatch.setattr(attachment_service, "get_storage", lambda: storage)

    await purge_record_attachments(db, "object", record_id)

    db.delete.assert_awaited_once_with(rows[0])


@pytest.mark.asyncio
async def test_purge_without_attachments_touches_no_storage(monkeypatch) -> None:
    db = _rows_db([])
    storage = MagicMock()
    storage.delete = AsyncMock()
    monkeypatch.setattr(attachment_service, "get_storage", lambda: storage)
    await purge_record_attachments(db, "place", uuid.uuid4())
    storage.delete.assert_not_called()
    db.delete.assert_not_called()


# --- attachments-gc ----------------------------------------------------------------------


def _gc_db(candidates, *owner_snapshot_results) -> AsyncMock:
    """execute() order: candidates, then per owner group (owner row, snapshots if owner exists)."""
    db = AsyncMock()
    results = []
    cand = MagicMock()
    cand.scalars.return_value.all.return_value = list(candidates)
    results.append(cand)
    for owner, snapshots in owner_snapshot_results:
        first = MagicMock()
        first.first.return_value = None if owner is None else (owner,)
        results.append(first)
        if owner is not None:
            snaps = MagicMock()
            snaps.scalars.return_value.all.return_value = list(snapshots)
            results.append(snaps)
    db.execute = AsyncMock(side_effect=results)
    return db


def _storage(monkeypatch) -> MagicMock:
    storage = MagicMock()
    storage.delete = AsyncMock()
    monkeypatch.setattr(attachment_service, "get_storage", lambda: storage)
    return storage


@pytest.mark.asyncio
async def test_gc_keeps_referenced_and_deletes_unreferenced(monkeypatch) -> None:
    old = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=30)
    record_meta = uuid.uuid4()
    record_snap = uuid.uuid4()
    record_none = uuid.uuid4()
    in_meta = _attachment(record_meta, created_at=old)
    in_snap = _attachment(record_snap, created_at=old)
    unused = _attachment(record_none, created_at=old)
    storage = _storage(monkeypatch)

    db = _gc_db(
        [in_meta, in_snap, unused],
        ({"vertrag": [{"id": str(in_meta.id)}]}, []),
        (
            {"vertrag": []},
            [{"vertrag": [{"id": str(in_snap.id)}]}],
        ),
        ({"vertrag": []}, []),
    )
    report = await gc_attachments(db, older_than=timedelta(days=7), dry_run=False)

    assert report == {"candidates": 3, "referenced": 2, "orphaned": 0, "deleted": 1, "failed": 0}
    storage.delete.assert_awaited_once_with(unused.storage_key)
    db.delete.assert_awaited_once_with(unused)
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_gc_deletes_orphans_of_missing_records(monkeypatch) -> None:
    old = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=30)
    orphan = _attachment(uuid.uuid4(), created_at=old)
    storage = _storage(monkeypatch)
    db = _gc_db([orphan], (None, []))

    report = await gc_attachments(db, older_than=timedelta(days=7), dry_run=False)

    assert report["orphaned"] == 1 and report["deleted"] == 1
    storage.delete.assert_awaited_once_with(orphan.storage_key)


@pytest.mark.asyncio
async def test_gc_dry_run_deletes_nothing(monkeypatch) -> None:
    old = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=30)
    orphan = _attachment(uuid.uuid4(), created_at=old)
    storage = _storage(monkeypatch)
    db = _gc_db([orphan], (None, []))

    report = await gc_attachments(db, older_than=timedelta(days=7), dry_run=True)

    assert report["deleted"] == 1
    storage.delete.assert_not_called()
    db.delete.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_gc_keeps_row_when_storage_delete_fails(monkeypatch) -> None:
    old = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=30)
    orphan = _attachment(uuid.uuid4(), created_at=old)
    storage = _storage(monkeypatch)
    storage.delete.side_effect = StorageDeleteError({orphan.storage_key: "denied"})
    db = _gc_db([orphan], (None, []))

    report = await gc_attachments(db, older_than=timedelta(days=7), dry_run=False)

    assert report["failed"] == 1 and report["deleted"] == 0
    db.delete.assert_not_called()


@pytest.mark.asyncio
async def test_gc_only_queries_rows_older_than_cutoff(monkeypatch) -> None:
    _storage(monkeypatch)
    db = _gc_db([])
    await gc_attachments(db, older_than=timedelta(days=7), dry_run=False)
    first_statement = str(db.execute.await_args_list[0].args[0])
    assert "attachments.created_at <" in first_statement


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("7d", timedelta(days=7)),
        ("12h", timedelta(hours=12)),
        ("0", timedelta(0)),
        (" 3D ", timedelta(days=3)),
    ],
)
def test_parse_older_than_accepts_days_hours_and_zero(value: str, expected: timedelta) -> None:
    assert parse_older_than(value) == expected


@pytest.mark.parametrize("value", ["7", "d", "-1d", "7w", "", "1.5d"])
def test_parse_older_than_rejects_other_forms(value: str) -> None:
    with pytest.raises(ValueError):
        parse_older_than(value)
