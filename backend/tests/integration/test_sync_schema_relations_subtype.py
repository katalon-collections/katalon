# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid

import pytest
from sqlalchemy import func, select

from katalon.core.models import Entity, FieldDefinition, Occurrence, Relation
from katalon.services.relation_service import sync_schema_relations


def _field(name: str, subtype: str | None, *, parent_id: uuid.UUID | None = None, ftype: str = "relation"):
    return FieldDefinition(
        target_type="occurrence", target_subtype=subtype, name=name, label={"de": name},
        field_type=ftype, parent_id=parent_id, is_repeatable=ftype == "relation" and parent_id is None,
        settings={"target_type": "entity"} if ftype == "relation" else {},
    )


async def _rows(session, record_id) -> list[Relation]:
    return list((await session.execute(select(Relation).where(Relation.from_id == record_id))).scalars())


def _entry(target) -> dict:
    return {"id": str(target.id), "label": "Ziel", "relation_type": "rel-x"}


@pytest.mark.asyncio
async def test_same_named_fields_of_different_subtypes_create_one_row(app) -> None:
    from katalon.database import AsyncSessionLocal

    s = uuid.uuid4().hex[:8]
    work, manifestation = f"work_{s}", f"man_{s}"
    async with AsyncSessionLocal() as session:
        target = Entity(metadata_={"label": "Ziel"}, status="draft")
        record = Occurrence(occurrence_type=work, metadata_={}, status="draft")
        session.add_all([
            target, record, _field(f"expression_{s}", work), _field(f"expression_{s}", manifestation),
        ])
        await session.flush()
        metadata = {f"expression_{s}": [_entry(target)]}

        # subtype read from the record
        await sync_schema_relations(session, "occurrence", record.id, metadata)
        rows = await _rows(session, record.id)
        assert len(rows) == 1 and rows[0].metadata_["source_field"] == f"expression_{s}"

        # idempotent, and an explicitly passed subtype gives the same result
        await sync_schema_relations(session, "occurrence", record.id, metadata, work)
        assert len(await _rows(session, record.id)) == 1
        await session.rollback()


@pytest.mark.asyncio
async def test_null_subtype_field_applies_to_all_but_other_subtype_field_does_not(app) -> None:
    from katalon.database import AsyncSessionLocal

    s = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        target = Entity(metadata_={"label": "Ziel"}, status="draft")
        record = Occurrence(occurrence_type=f"a_{s}", metadata_={}, status="draft")
        plain = Occurrence(metadata_={}, status="draft")  # no subtype at all
        session.add_all([
            target, record, plain,
            _field(f"alle_{s}", None), _field(f"nur_b_{s}", f"b_{s}"),
        ])
        await session.flush()
        metadata = {f"alle_{s}": [_entry(target)], f"nur_b_{s}": [_entry(target)]}

        await sync_schema_relations(session, "occurrence", record.id, metadata)
        assert {r.metadata_["source_field"] for r in await _rows(session, record.id)} == {f"alle_{s}"}
        # a record without subtype only gets fields without one
        await sync_schema_relations(session, "occurrence", plain.id, metadata)
        assert {r.metadata_["source_field"] for r in await _rows(session, plain.id)} == {f"alle_{s}"}
        await session.rollback()


@pytest.mark.asyncio
async def test_group_relation_children_follow_the_group_subtype(app) -> None:
    from katalon.database import AsyncSessionLocal

    s = uuid.uuid4().hex[:8]
    work, manifestation = f"work_{s}", f"man_{s}"
    async with AsyncSessionLocal() as session:
        target = Entity(metadata_={"label": "Ziel"}, status="draft")
        record = Occurrence(occurrence_type=work, metadata_={}, status="draft")
        g_work = _field(f"personen_{s}", work, ftype="group")
        g_man = _field(f"personen_{s}", manifestation, ftype="group")
        session.add_all([target, record, g_work, g_man])
        await session.flush()
        session.add_all([
            _field(f"person_{s}", work, parent_id=g_work.id),
            _field(f"person_{s}", manifestation, parent_id=g_man.id),
        ])
        await session.flush()
        metadata = {f"personen_{s}": [{f"person_{s}": _entry(target)}]}

        await sync_schema_relations(session, "occurrence", record.id, metadata)
        rows = await _rows(session, record.id)
        assert len(rows) == 1
        assert rows[0].metadata_["source_field"] == f"personen_{s}.person_{s}"
        await session.rollback()


@pytest.mark.asyncio
async def test_a_repeated_target_in_one_field_creates_one_row(app) -> None:
    from katalon.database import AsyncSessionLocal

    s = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        target = Entity(metadata_={"label": "Ziel"}, status="draft")
        record = Occurrence(occurrence_type=f"w_{s}", metadata_={}, status="draft")
        field = _field(f"expr_{s}", None)
        field.is_repeatable = True
        session.add_all([target, record, field])
        await session.flush()
        await sync_schema_relations(
            session, "occurrence", record.id, {f"expr_{s}": [_entry(target), _entry(target)]}
        )
        assert len(await _rows(session, record.id)) == 1
        await session.rollback()


@pytest.mark.asyncio
async def test_resync_dry_run_reports_duplicates_without_writing_and_real_run_removes_them(app) -> None:
    from katalon.database import AsyncSessionLocal
    from katalon.management.resync_relations import resync

    s = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        target = Entity(metadata_={"label": "Ziel"}, status="draft")
        record = Occurrence(occurrence_type=f"w_{s}", metadata_={f"expr_{s}": [{}]}, status="draft")
        field = _field(f"expr_{s}", None)
        field.is_repeatable = True
        session.add_all([target, record, field])
        await session.flush()
        record.metadata_ = {f"expr_{s}": [_entry(target)]}
        for _ in range(3):  # three identical rows: what the old sync produced
            session.add(Relation(
                from_type="occurrence", from_id=record.id, to_type="entity", to_id=target.id,
                relation_type="rel-x", metadata_={"source_field": f"expr_{s}"}, is_schema_derived=True,
            ))
        await session.commit()
        record_id = record.id

    dry = await resync(AsyncSessionLocal, dry_run=True)
    assert dry.extra_rows >= 2 and dry.duplicate_groups >= 1 and dry.extra_rows_after is None
    async with AsyncSessionLocal() as session:
        count = await session.scalar(select(func.count()).select_from(Relation).where(Relation.from_id == record_id))
    assert count == 3  # dry run wrote nothing

    real = await resync(AsyncSessionLocal, dry_run=False)
    assert real.extra_rows_after == 0
    async with AsyncSessionLocal() as session:
        count = await session.scalar(select(func.count()).select_from(Relation).where(Relation.from_id == record_id))
    assert count == 1
