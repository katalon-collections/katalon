# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Lifecycle coverage for purge-only relation cleanup."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select


async def _add_relation_fields(session, record_type: str) -> tuple[str, str, str, str]:
    from katalon.core.models import FieldDefinition

    marker = uuid.uuid4().hex[:8]
    direct = FieldDefinition(
        target_type=record_type,
        name=f"purge_direct_{record_type}_{marker}",
        label={"de": "Direktbezug"},
        field_type="relation",
        is_repeatable=True,
        settings={"target_type": "entity"},
    )
    scalar = FieldDefinition(
        target_type=record_type,
        name=f"purge_scalar_{record_type}_{marker}",
        label={"de": "Einzelbezug"},
        field_type="relation",
        settings={"target_type": "entity"},
    )
    group = FieldDefinition(
        id=uuid.uuid4(),
        target_type=record_type,
        name=f"purge_group_{record_type}_{marker}",
        label={"de": "Gruppenbezug"},
        field_type="group",
        is_repeatable=True,
    )
    child = FieldDefinition(
        target_type=record_type,
        name=f"purge_target_{marker}",
        label={"de": "Ziel"},
        field_type="relation",
        parent_id=group.id,
        settings={"target_type": "entity"},
    )
    session.add_all((direct, scalar, group, child))
    return direct.name, scalar.name, group.name, child.name


def _source_record(
    record_type: str,
    model: type,
    direct_field: str,
    scalar_field: str,
    group_field: str,
    child_field: str,
    target_id: uuid.UUID,
    survivor_id: uuid.UUID,
):
    metadata = {
        direct_field: [
            {"id": str(target_id), "label": "purge target"},
            {"id": str(survivor_id), "label": "survives"},
        ],
        scalar_field: {"id": str(target_id), "label": "purge target"},
        group_field: [
            {
                child_field: {"id": str(target_id), "label": "purge target"},
                "note": "kept",
            }
        ],
    }
    values = {
        "idno": f"PURGE-SOURCE-{record_type}-{uuid.uuid4().hex[:10]}",
        "metadata_": metadata,
    }
    if record_type in {"object", "entity", "place", "occurrence", "collection"}:
        values["status"] = "draft"
    if record_type == "procedure":
        values["procedure_type"] = "loan_out"
    return model(**values)


@pytest.mark.asyncio
async def test_purge_cleans_direct_and_group_references_for_all_source_types_and_reindexes(
    app, monkeypatch
) -> None:
    """A purge updates every surviving source type atomically and only once."""
    import katalon.database as database_module
    from katalon.core.models import (
        AuditLog,
        Collection,
        Entity,
        Object,
        Occurrence,
        Place,
        Procedure,
        Relation,
        StorageLocation,
    )
    from katalon.workers import purge_tasks
    from katalon.workers.index_tasks import index_record_task

    source_models = {
        "object": Object,
        "entity": Entity,
        "place": Place,
        "occurrence": Occurrence,
        "procedure": Procedure,
        "collection": Collection,
        "storage_location": StorageLocation,
    }
    target_id = uuid.uuid4()
    survivor_id = uuid.uuid4()
    old_cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=999)
    sources: dict[str, tuple[uuid.UUID, str, str, str, str]] = {}
    async with database_module.AsyncSessionLocal() as session:
        session.add(
            Entity(
                id=target_id,
                idno=f"PURGE-TARGET-{uuid.uuid4().hex[:10]}",
                entity_type="person",
                status="draft",
                metadata_={},
                deleted_at=old_cutoff,
            )
        )
        for record_type, model in source_models.items():
            direct, scalar, group, child = await _add_relation_fields(session, record_type)
            source = _source_record(
                record_type,
                model,
                direct,
                scalar,
                group,
                child,
                target_id,
                survivor_id,
            )
            session.add(source)
            await session.flush()
            sources[record_type] = (source.id, direct, scalar, group, child)
            session.add(
                Relation(
                    from_type=record_type,
                    from_id=source.id,
                    to_type="entity",
                    to_id=target_id,
                    relation_type="references",
                )
            )
        await session.commit()

    dispatched: list[tuple[tuple, dict]] = []
    monkeypatch.setattr(
        index_record_task,
        "delay",
        lambda *args, **kwargs: dispatched.append((args, kwargs)),
    )
    monkeypatch.setattr("katalon.config.settings.oxigraph_enabled", False)

    totals = await purge_tasks._do_purge()
    assert totals["entity"] == 1

    async with database_module.AsyncSessionLocal() as session:
        assert await session.get(Entity, target_id) is None
        for record_type, model in source_models.items():
            source_id, direct, scalar, group, child = sources[record_type]
            source = await session.get(model, source_id)
            assert source is not None
            assert source.metadata_[direct] == [{"id": str(survivor_id), "label": "survives"}]
            assert source.metadata_[scalar] is None
            assert source.metadata_[group] == [{child: None, "note": "kept"}]
        assert (
            not (
                await session.execute(
                    select(Relation).where(
                        Relation.to_type == "entity", Relation.to_id == target_id
                    )
                )
            )
            .scalars()
            .all()
        )
        cleanup_audits = (
            (
                await session.execute(
                    select(AuditLog.record_type).where(
                        AuditLog.action == "relation_cleanup",
                        AuditLog.record_id.in_([source_id for source_id, *_ in sources.values()]),
                    )
                )
            )
            .scalars()
            .all()
        )
        assert set(cleanup_audits) == set(source_models)

    assert {(args[0], args[1]) for args, _ in dispatched} == {
        (record_type, str(source_id)) for record_type, (source_id, *_fields) in sources.items()
    }

    retry_totals = await purge_tasks._do_purge()
    assert retry_totals["entity"] == 0
    assert len(dispatched) == len(source_models)


@pytest.mark.asyncio
async def test_hard_delete_procedure_cleans_direct_and_group_references(
    app, async_client, auth_headers
) -> None:
    import katalon.database as database_module
    from katalon.core.models import (
        AuditLog,
        Entity,
        FieldDefinition,
        Procedure,
        Relation,
    )

    marker = uuid.uuid4().hex[:8]
    procedure_id = uuid.uuid4()
    direct_name = f"procedure_direct_{marker}"
    group_name = f"procedure_group_{marker}"
    child_name = f"procedure_child_{marker}"
    async with database_module.AsyncSessionLocal() as session:
        group = FieldDefinition(
            id=uuid.uuid4(),
            target_type="entity",
            name=group_name,
            label={"de": "Gruppe"},
            field_type="group",
            is_repeatable=True,
        )
        session.add_all(
            (
                FieldDefinition(
                    target_type="entity",
                    name=direct_name,
                    label={"de": "Direktbezug"},
                    field_type="relation",
                    settings={"target_type": "procedure"},
                ),
                group,
                FieldDefinition(
                    target_type="entity",
                    name=child_name,
                    label={"de": "Gruppenbezug"},
                    field_type="relation",
                    parent_id=group.id,
                    settings={"target_type": "procedure"},
                ),
                Procedure(
                    id=procedure_id,
                    idno=f"PURGE-PROCEDURE-{marker}",
                    procedure_type="loan_out",
                    status="draft",
                    metadata_={},
                ),
            )
        )
        source = Entity(
            idno=f"PROCEDURE-SOURCE-{marker}",
            entity_type="person",
            status="draft",
            metadata_={
                direct_name: {"id": str(procedure_id), "label": "procedure"},
                group_name: [{child_name: {"id": str(procedure_id), "label": "procedure"}}],
            },
        )
        session.add(source)
        await session.flush()
        source_id = source.id
        session.add(
            Relation(
                from_type="entity",
                from_id=source_id,
                to_type="procedure",
                to_id=procedure_id,
                relation_type="references",
            )
        )
        await session.commit()

    deleted = await async_client.delete(
        f"/v1/procedures/{procedure_id}?force=true", headers=auth_headers
    )
    assert deleted.status_code == 204, deleted.text

    async with database_module.AsyncSessionLocal() as session:
        source = await session.get(Entity, source_id)
        assert source is not None
        assert source.metadata_[direct_name] is None
        assert source.metadata_[group_name] == [{child_name: None}]
        assert (
            not (await session.execute(select(Relation).where(Relation.to_id == procedure_id)))
            .scalars()
            .all()
        )
        assert (
            await session.execute(
                select(AuditLog).where(
                    AuditLog.record_id == source_id,
                    AuditLog.action == "relation_cleanup",
                )
            )
        ).scalar_one_or_none() is not None
