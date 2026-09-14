# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Import-task resilience tests (katalon issue #382).

``import_records_task`` runs the whole CSV/Excel import inside a single
SQLAlchemy transaction that is committed exactly once, after every row has
been processed (see ``katalon/workers/import_tasks.py``). These tests prove
the resulting invariant: any failure before that final commit — a worker
crash, a dropped DB connection, an unexpected exception — must not leave a
half-imported batch in the database. There is no per-row commit to roll back
partially, so "the worker died mid-import" and "a DB call raised" produce the
identical, already-tested code path exercised here.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest
import sqlalchemy.ext.asyncio as sa_asyncio
from sqlalchemy import select

from katalon.core.models import AuditLog, Entity, FieldDefinition, Object, Relation, User


class _FakeRedis:
    """Stand-in for redis.from_url — the import task's cancel-check only calls .get()."""

    def get(self, key: str) -> None:
        return None


def _patch_no_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    from katalon.workers.import_tasks import import_records_task

    monkeypatch.setattr("redis.from_url", lambda *args, **kwargs: _FakeRedis())
    monkeypatch.setattr(import_records_task, "update_state", lambda **kwargs: None)


async def _admin_user_id() -> str:
    from katalon.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(User.email == "admin@katalon.dev"))
        assert user is not None
        return str(user.id)


def _fail_flush_after(monkeypatch: pytest.MonkeyPatch, fail_at_call: int) -> None:
    """Make the Nth AsyncSession.flush() call raise, simulating a dropped DB
    connection or the worker process being killed at that point."""
    original_flush = sa_asyncio.AsyncSession.flush
    call_count = {"n": 0}

    async def flaky_flush(self: Any, *args: Any, **kwargs: Any) -> None:
        call_count["n"] += 1
        if call_count["n"] == fail_at_call:
            raise ConnectionError("simulated DB connection drop")
        return await original_flush(self, *args, **kwargs)

    monkeypatch.setattr(sa_asyncio.AsyncSession, "flush", flaky_flush)


@pytest.mark.asyncio
async def test_import_failure_mid_batch_leaves_no_partial_records(
    app, auth_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    from katalon.database import AsyncSessionLocal
    from katalon.workers.import_tasks import import_records_task

    _patch_no_broker(monkeypatch)
    # 5 rows create 5 flushes (one per new record); fail on the 3rd so two
    # records would already be flushed (visible in-transaction) when the
    # error hits — the assertion below proves that visibility does not
    # survive because the batch never reaches its single final commit().
    _fail_flush_after(monkeypatch, fail_at_call=3)
    marker = f"IMPORT-CRASH-{uuid.uuid4().hex}"
    rows = [{"title": f"{marker} row {i}"} for i in range(5)]

    user_id = await _admin_user_id()
    with pytest.raises(ConnectionError):
        await asyncio.to_thread(
            import_records_task.run,
            "object",
            rows,
            {"title": "label"},
            user_id=user_id,
        )

    async with AsyncSessionLocal() as session:
        persisted = (
            (
                await session.execute(
                    select(Object).where(Object.metadata_["label"].astext.like(f"{marker}%"))
                )
            )
            .scalars()
            .all()
        )
        assert persisted == []


@pytest.mark.asyncio
async def test_import_failure_reports_error_result_and_failure_notification(
    app, auth_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    from katalon.workers import import_tasks
    from katalon.workers.import_tasks import import_records_task

    _patch_no_broker(monkeypatch)
    _fail_flush_after(monkeypatch, fail_at_call=1)

    enqueued: list[tuple[Any, ...]] = []
    monkeypatch.setattr(import_tasks, "enqueue", lambda *args, **kwargs: enqueued.append(args))

    user_id = await _admin_user_id()
    with pytest.raises(ConnectionError):
        await asyncio.to_thread(
            import_records_task.run,
            "object",
            [{"title": "irrelevant"}],
            {"title": "label"},
            user_id=user_id,
        )

    assert len(enqueued) == 1
    _, user_id, subject, _text = enqueued[0]
    assert subject == "Katalon: Import fehlgeschlagen"


@pytest.mark.asyncio
async def test_import_worker_rechecks_execution_time_authorization(
    app, monkeypatch: pytest.MonkeyPatch
) -> None:
    from katalon.workers.import_tasks import import_records_task

    _patch_no_broker(monkeypatch)
    result = await asyncio.to_thread(
        import_records_task.run,
        "object",
        [{"title": "must-not-persist"}],
        {"title": "label"},
        user_id=str(uuid.uuid4()),
    )

    assert result["created"] == result["updated"] == 0
    assert result["errors"] == [
        {
            "row": None,
            "error": "Import-Job abgebrochen: Benutzer nicht gefunden oder deaktiviert.",
        }
    ]


@pytest.mark.asyncio
async def test_upsert_prepares_metadata_preserves_legacy_and_syncs_relations(
    app, auth_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    from katalon.database import AsyncSessionLocal
    from katalon.workers.import_tasks import import_records_task

    _patch_no_broker(monkeypatch)
    user_id = await _admin_user_id()
    idno = f"IMPORT-REPLACE-{uuid.uuid4().hex}"
    field_suffix = uuid.uuid4().hex
    locked_field = f"locked_{field_suffix}"
    defaulted_field = f"defaulted_{field_suffix}"
    relation_field = f"relation_{field_suffix}"
    title_field = f"title_{field_suffix}"

    async with AsyncSessionLocal() as session:
        target = Entity(metadata_={"label": "Target"})
        session.add(target)
        await session.flush()
        record = Object(
            idno=idno,
            metadata_={
                "legacy": "keep",
                locked_field: "protected",
                relation_field: {
                    "id": str(target.id),
                    "label": "Target",
                    "relation_type": "related",
                },
                title_field: "old value",
            },
        )
        session.add_all(
            [
                record,
                FieldDefinition(
                    target_type="object",
                    name=locked_field,
                    field_type="text",
                    settings={"is_locked": True},
                ),
                FieldDefinition(
                    target_type="object",
                    name=defaulted_field,
                    field_type="text",
                    settings={"default_value": "from-schema"},
                ),
                FieldDefinition(
                    target_type="object",
                    name=relation_field,
                    field_type="relation",
                    settings={"target_type": "entity"},
                ),
            ]
        )
        await session.commit()
        record_id, target_id = record.id, target.id
    merge_result = await asyncio.to_thread(
        import_records_task.run,
        "object",
        [{"idno": idno, "title": "replacement"}],
        {"idno": "__idno__", "title": title_field},
        idno_strategy="column",
        upsert_strategy="merge",
        user_id=user_id,
    )

    assert merge_result["updated"] == 1
    async with AsyncSessionLocal() as session:
        record = await session.get(Object, record_id)
        assert record is not None
        assert record.metadata_[title_field] == "old value"

    result = await asyncio.to_thread(
        import_records_task.run,
        "object",
        [{"idno": idno, "title": "replacement"}],
        {"idno": "__idno__", "title": title_field},
        idno_strategy="column",
        upsert_strategy="replace",
        user_id=user_id,
    )

    assert result["updated"] == 1
    assert result["errors"] == []
    async with AsyncSessionLocal() as session:
        record = await session.get(Object, record_id)
        assert record is not None
        assert record.metadata_ == {
            "legacy": "keep",
            locked_field: "protected",
            relation_field: {
                "id": str(target_id),
                "label": "Target",
                "relation_type": "related",
            },
            title_field: "replacement",
            defaulted_field: "from-schema",
        }
        relation = await session.scalar(
            select(Relation).where(
                Relation.from_type == "object",
                Relation.from_id == record_id,
                Relation.to_type == "entity",
                Relation.to_id == target_id,
                Relation.is_schema_derived.is_(True),
            )
        )
        assert relation is not None
        audits = (
            (
                await session.execute(
                    select(AuditLog).where(
                        AuditLog.record_type == "object",
                        AuditLog.record_id == record_id,
                        AuditLog.action == "update",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert any(f"metadata.{title_field}" in audit.changed_fields["new"] for audit in audits)

    # Field definitions here are global schema, not request-scoped — the
    # Postgres testcontainer is shared across the whole integration test
    # session, so an uncleaned defaulted_field would silently populate
    # `{"default_value": "from-schema"}` onto every "object" record created
    # by every test that runs afterward.
    async with AsyncSessionLocal() as session:
        await session.execute(
            FieldDefinition.__table__.delete().where(
                FieldDefinition.target_type == "object",
                FieldDefinition.name.in_([locked_field, defaulted_field, relation_field]),
            )
        )
        await session.commit()
