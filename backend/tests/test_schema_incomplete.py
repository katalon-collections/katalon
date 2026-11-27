# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from katalon.api.v1 import objects as objects_api
from katalon.core.models import (
    Collection,
    Entity,
    Object,
    Occurrence,
    Place,
    Procedure,
    StorageLocation,
)
from katalon.core.schemas import (
    CollectionRead,
    EntityRead,
    ObjectCreate,
    ObjectRead,
    OccurrenceRead,
    PlaceRead,
    ProcedureRead,
    StorageLocationRead,
)
from katalon.services.public_metadata_service import project_public_record
from katalon.services.schema_service import metadata_missing_required_fields, validate_metadata


def _field(
    name: str,
    *,
    is_required: bool = False,
    field_type: str = "text",
    is_repeatable: bool = False,
) -> MagicMock:
    f = MagicMock()
    f.id = uuid.uuid4()
    f.name = name
    f.is_required = is_required
    f.field_type = field_type
    f.is_repeatable = is_repeatable
    f.is_translatable = False
    f.settings = {}
    f.target_subtype = None
    return f


def test_missing_required_top_level_fields() -> None:
    fields = [
        _field("idno", is_required=True),
        _field("label", is_required=True),
        _field("rights", is_required=True),
        _field("count", is_required=True, field_type="number"),
        _field("flag", is_required=True, field_type="boolean"),
        _field("tags", is_required=True, is_repeatable=True),
        _field("notes", is_required=False),
    ]

    # idno is a native column and must be ignored in metadata checks; 0 and False count as present.
    missing = metadata_missing_required_fields(
        {
            "label": "Objekt",
            "rights": "",
            "count": 0,
            "flag": False,
            "tags": [],
        },
        fields,
        {},
    )
    assert missing == ["rights", "tags"]


def test_missing_required_group_and_subfields() -> None:
    req_group = _field("measurements", is_required=True, field_type="group", is_repeatable=True)
    opt_group = _field("provenance", is_required=False, field_type="group", is_repeatable=True)
    sub_unit = _field("unit", is_required=True)
    sub_owner = _field("owner", is_required=True)

    sub_map = {
        req_group.id: [sub_unit],
        opt_group.id: [sub_owner],
    }

    # Empty required group is missing; empty optional group is not.
    assert metadata_missing_required_fields({}, [req_group, opt_group], sub_map) == [
        "measurements"
    ]

    # Non-empty optional group missing a required subfield is flagged.
    assert metadata_missing_required_fields(
        {
            "measurements": [{"unit": "cm"}],
            "provenance": [{"owner": ""}],
        },
        [req_group, opt_group],
        sub_map,
    ) == ["provenance.owner"]

    # Complete group instances pass.
    assert (
        metadata_missing_required_fields(
            {
                "measurements": [{"unit": "cm"}],
                "provenance": [{"owner": "Sammlung A"}],
            },
            [req_group, opt_group],
            sub_map,
        )
        == []
    )


@pytest.mark.asyncio
async def test_public_projection_masks_schema_incomplete() -> None:
    now = datetime.now(UTC)
    record = ObjectRead(
        id=uuid.uuid4(),
        idno="OBJ-1",
        status="public",
        metadata_={"label": "Public Object"},
        schema_incomplete=True,
        created_at=now,
        updated_at=now,
        version=1,
    )
    projected = await project_public_record(
        AsyncMock(),
        record,
        "object",
        None,
        fields=[_field("label")],
        hidden_targets=set(),
    )
    assert projected.schema_incomplete is False


def test_read_schemas_default_schema_incomplete_for_unpersisted_and_mock_objects() -> None:
    now = datetime.now(UTC)
    cases = [
        (
            ObjectRead,
            Object(
                id=uuid.uuid4(),
                idno="OBJ-1",
                status="public",
                collection_status="active",
                metadata_={},
                ai_provenance={},
                created_at=now,
                updated_at=now,
                version=1,
            ),
        ),
        (
            EntityRead,
            Entity(
                id=uuid.uuid4(),
                idno="ENT-1",
                status="public",
                metadata_={},
                ai_provenance={},
                created_at=now,
                updated_at=now,
                version=1,
            ),
        ),
        (
            PlaceRead,
            Place(
                id=uuid.uuid4(),
                idno="PLC-1",
                status="public",
                metadata_={},
                ai_provenance={},
                created_at=now,
                updated_at=now,
                version=1,
            ),
        ),
        (
            OccurrenceRead,
            Occurrence(
                id=uuid.uuid4(),
                idno="OCC-1",
                status="public",
                metadata_={},
                ai_provenance={},
                created_at=now,
                updated_at=now,
                version=1,
            ),
        ),
        (
            CollectionRead,
            Collection(
                id=uuid.uuid4(),
                idno="COL-1",
                status="public",
                metadata_={},
                ai_provenance={},
                created_at=now,
                updated_at=now,
                version=1,
            ),
        ),
        (
            StorageLocationRead,
            StorageLocation(
                id=uuid.uuid4(),
                idno="LOC-1",
                metadata_={},
                ai_provenance={},
                created_at=now,
                updated_at=now,
                version=1,
            ),
        ),
        (
            ProcedureRead,
            Procedure(
                id=uuid.uuid4(),
                idno="PRC-1",
                procedure_type="loan_out",
                status="draft",
                metadata_={},
                ai_provenance={},
                created_at=now,
                updated_at=now,
                version=1,
            ),
        ),
    ]
    for schema_cls, orm_obj in cases:
        assert orm_obj.schema_incomplete is None
        validated = schema_cls.model_validate(orm_obj)
        assert validated.schema_incomplete is False

    mock_obj = SimpleNamespace(
        id=uuid.uuid4(),
        idno="OBJ-MOCK",
        object_type=None,
        collection_status="active",
        status="draft",
        metadata_={},
        ai_provenance={},
        created_at=now,
        updated_at=now,
        deleted_at=None,
        version=1,
    )
    assert ObjectRead.model_validate(mock_obj).schema_incomplete is False

    mock_obj.schema_incomplete = True
    assert ObjectRead.model_validate(mock_obj).schema_incomplete is True


@pytest.mark.asyncio
async def test_update_object_rechecks_and_clears_schema_incomplete_on_save() -> None:
    now = datetime.now(UTC)
    obj = Object(
        id=uuid.uuid4(),
        idno="OBJ-RECHECK",
        object_type=None,
        collection_status="active",
        status="draft",
        schema_incomplete=True,
        metadata_={"label": "Altbestand"},
        ai_provenance={},
        created_at=now,
        updated_at=now,
        version=1,
    )
    user = SimpleNamespace(id=uuid.uuid4(), role="admin")
    required_fields = [_field("label", is_required=True), _field("rights", is_required=True)]

    db = AsyncMock()
    lookup_res = MagicMock()
    lookup_res.scalar_one_or_none.return_value = obj
    unique_res = MagicMock()
    unique_res.scalar_one_or_none.return_value = None

    with (
        patch.object(objects_api, "enforce_not_blocked", AsyncMock()),
        patch.object(objects_api, "enforce_not_locked", AsyncMock()),
        patch.object(objects_api, "ensure_subtype_exists", AsyncMock()),
        patch.object(objects_api, "prepare_metadata", AsyncMock(side_effect=lambda _db, _t, m, *_a, **_kw: dict(m))),
        patch.object(objects_api, "flush_record", AsyncMock()),
        patch.object(objects_api, "sync_schema_relations", AsyncMock()),
        patch.object(objects_api, "log_change", AsyncMock()),
        patch.object(objects_api.search_service, "index_record", AsyncMock()),
        patch("katalon.services.schema_service.get_field_definitions", AsyncMock(return_value=required_fields)),
    ):
        # Draft save without the required field keeps schema_incomplete=True.
        db.execute.side_effect = [lookup_res, unique_res]
        draft_missing = await objects_api.update_object(
            obj.id,
            ObjectCreate(idno="OBJ-RECHECK", status="draft", metadata_={"label": "Altbestand"}),
            db,
            current_user=user,
            if_match=1,
        )
        assert draft_missing.schema_incomplete is True

        # Filling the missing required field and saving as draft clears schema_incomplete.
        db.execute.side_effect = [lookup_res, unique_res]
        draft_complete = await objects_api.update_object(
            obj.id,
            ObjectCreate(
                idno="OBJ-RECHECK",
                status="draft",
                metadata_={"label": "Altbestand", "rights": "CC0"},
            ),
            db,
            current_user=user,
            if_match=1,
        )
        assert draft_complete.schema_incomplete is False

        # Saving as internal clears schema_incomplete after required-field validation passes.
        obj.schema_incomplete = True
        db.execute.side_effect = [lookup_res, unique_res]
        internal_complete = await objects_api.update_object(
            obj.id,
            ObjectCreate(
                idno="OBJ-RECHECK",
                status="internal",
                metadata_={"label": "Altbestand", "rights": "CC0"},
            ),
            db,
            current_user=user,
            if_match=1,
        )
        assert internal_complete.schema_incomplete is False


@pytest.mark.parametrize(("subtype", "expected"), [(None, 0), ("b", 0), ("a", 1)])
@pytest.mark.asyncio
async def test_required_subtype_field_binds_only_that_subtype(subtype: str | None, expected: int) -> None:
    scoped = _field("only_a", is_required=True)
    scoped.target_subtype = "a"
    with patch(
        "katalon.services.schema_service.get_field_definitions", AsyncMock(return_value=[scoped])
    ):
        errors = await validate_metadata(AsyncMock(), "object", {}, subtype)
    assert len(errors) == expected
