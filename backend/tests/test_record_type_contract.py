# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Cross-cutting contract for the seven supported core record types."""

import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from katalon.api.v1 import idno, index_health, portal_public
from katalon.core import visibility
from katalon.core.models import Procedure
from katalon.core.schemas import RECORD_TYPES
from katalon.services import (
    audit_service,
    batch_service,
    export_service,
    relation_cleanup_service,
    relation_service,
    working_set_service,
)
from katalon.workers import index_tasks, purge_tasks

CORE_TYPES = frozenset(RECORD_TYPES)
CAPABILITY_MATRIX = {
    "idno_preview": CORE_TYPES,
    "index_health": CORE_TYPES,
    "reconciliation": CORE_TYPES,
    "cascade_reindex": CORE_TYPES,
    "relation_cleanup": CORE_TYPES,
    "json_csv_export": CORE_TYPES,
    "soft_delete_purge": CORE_TYPES - {"procedure"},
    "portal_public_visibility": frozenset(
        {"object", "entity", "place", "occurrence", "collection"}
    ),
    "batch_edit": CORE_TYPES,
    "batch_subtype": CORE_TYPES,
    "relation_service": CORE_TYPES,
    "working_set": CORE_TYPES,
    "searchable_visibility": CORE_TYPES,
    "core_schemas": CORE_TYPES,
    "audit_logging": CORE_TYPES,
}


def test_core_record_type_capability_contract() -> None:
    """Every cross-cutting registry covers all core types unless explicitly excluded."""
    registries = {
        "index_health": frozenset(index_health._MODEL_MAP),
        "reconciliation": frozenset(index_tasks._record_models()),
        "cascade_reindex": frozenset(index_tasks._record_models()),
        "json_csv_export": frozenset(export_service.RECORD_MODELS),
        "batch_edit": frozenset(batch_service._MODEL_MAP),
        "batch_subtype": frozenset(batch_service._SUBTYPE_KEY),
        "relation_service": frozenset(relation_service._RECORD_MODELS),
        "working_set": frozenset(working_set_service._RECORD_MODELS),
        "searchable_visibility": frozenset(visibility.SEARCHABLE_RECORD_TYPES),
        "core_schemas": frozenset(RECORD_TYPES),
        "audit_logging": frozenset(audit_service._LOGGABLE_RECORD_TYPES),
    }

    assert CAPABILITY_MATRIX["idno_preview"] == CORE_TYPES
    assert registries == {capability: CAPABILITY_MATRIX[capability] for capability in registries}

    # Soft-delete purge covers all core types with deleted_at (excludes procedure)
    assert frozenset(purge_tasks._PURGEABLE_MODELS) == CAPABILITY_MATRIX["soft_delete_purge"]
    assert frozenset(purge_tasks._MODEL_MAP) == CAPABILITY_MATRIX["soft_delete_purge"]
    soft_delete_types = {
        record_type
        for record_type, model in index_tasks._record_models().items()
        if hasattr(model, "deleted_at")
    }
    assert soft_delete_types == CAPABILITY_MATRIX["soft_delete_purge"]
    assert not hasattr(Procedure, "deleted_at")

    # Procedure and storage locations remain internal-only; the portal is public only
    # for object/entity/place/occurrence/collection.
    assert frozenset(portal_public._PUBLIC_TYPES) == CAPABILITY_MATRIX["portal_public_visibility"]


@pytest.mark.asyncio
async def test_idno_preview_supports_all_core_types(monkeypatch) -> None:
    config = SimpleNamespace(idno_schemas=dict.fromkeys(RECORD_TYPES, "{counter}"))

    class PreviewDB:
        async def execute(self, _statement):
            return SimpleNamespace(scalar_one_or_none=lambda: config)

    async def preview(_db, record_type, _schema):
        return f"{record_type}-1"

    monkeypatch.setattr(idno, "peek_next_idno", preview)
    previews = {
        record_type: (await idno.get_next_idno(PreviewDB(), record_type, None)).next
        for record_type in RECORD_TYPES
    }

    assert previews == {record_type: f"{record_type}-1" for record_type in RECORD_TYPES}


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return SimpleNamespace(all=lambda: self.rows)


class _RelationCleanupSession:
    def __init__(self):
        self._field_query = True
        self.queried_models = set()

    async def execute(self, statement):
        if self._field_query:
            self._field_query = False
            fields = [
                SimpleNamespace(
                    field_type="relation",
                    settings={"target_type": "object"},
                    parent_id=None,
                    target_type=record_type,
                    name="relation",
                )
                for record_type in RECORD_TYPES
            ]
            return _Result(fields)
        self.queried_models.add(statement.column_descriptions[0]["entity"])
        return _Result([])


@pytest.mark.asyncio
async def test_relation_cleanup_supports_all_core_source_types() -> None:
    session = _RelationCleanupSession()

    assert (
        await relation_cleanup_service.cleanup_relation_refs(session, "object", uuid.uuid4()) == 0
    )
    assert frozenset(model.__tablename__ for model in session.queried_models) == {
        model.__tablename__ for model in index_tasks._record_models().values()
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("record_type", "subtype_field", "status"),
    [
        ("procedure", "procedure_type", "draft"),
        ("storage_location", "storage_location_type", None),
    ],
)
async def test_json_csv_export_supports_procedure_and_storage_location(
    monkeypatch, record_type: str, subtype_field: str, status: str | None
) -> None:
    record = SimpleNamespace(
        id=uuid.uuid4(),
        idno=f"{record_type}-1",
        metadata_={"label": record_type},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        **{subtype_field: "test"},
    )
    if status is not None:
        record.status = status

    async def load_records(*_args):
        return [record], []

    monkeypatch.setattr(export_service, "_load_records", load_records)
    csv_export = "".join(
        [chunk async for chunk in export_service.stream_csv(None, record_type, None, None)]
    )
    json_export = json.loads(
        "".join(
            [chunk async for chunk in export_service.stream_json(None, record_type, None, None)]
        )
    )

    assert record.idno in csv_export
    assert json_export == [
        {
            "id": str(record.id),
            "idno": record.idno,
            "subtype": "test",
            "status": status,
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
            "metadata": record.metadata_,
        }
    ]
