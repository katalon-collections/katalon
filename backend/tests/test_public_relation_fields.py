# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Relation field values must not expose drafts or internal records to the public."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from katalon.services.public_metadata_service import (
    filter_public_metadata,
    load_hidden_relation_targets,
    relation_target_ids,
)

PUBLIC = str(uuid.uuid4())
DRAFT = str(uuid.uuid4())


def _field(name: str, *, parent_id: uuid.UUID | None = None, field_type: str = "relation") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(), name=name, parent_id=parent_id, field_type=field_type, target_subtype=None,
        settings={"target_type": "entity"} if field_type == "relation" else {},
    )


def _entry(target: str) -> dict[str, str]:
    return {"id": target, "label": f"Name {target[:4]}", "relation_type": "schenker"}


def test_hidden_targets_are_dropped_from_relation_fields_and_groups() -> None:
    group = _field("beteiligte", field_type="group")
    fields = [_field("schenker"), _field("verlag"), group, _field("person", parent_id=group.id)]
    stored = {
        "schenker": [_entry(PUBLIC), _entry(DRAFT)],
        "verlag": _entry(DRAFT),
        "beteiligte": [{"person": _entry(DRAFT)}, {"person": _entry(PUBLIC)}],
    }

    projected = filter_public_metadata(stored, fields, hidden_targets={DRAFT})

    assert projected["schenker"] == [_entry(PUBLIC)]
    assert "verlag" not in projected
    assert projected["beteiligte"] == [{"person": _entry(PUBLIC)}]


def test_relation_fields_are_withheld_when_targets_were_not_checked() -> None:
    fields = [_field("schenker"), _field("titel", field_type="text")]

    projected = filter_public_metadata({"schenker": [_entry(PUBLIC)], "titel": "T"}, fields)

    assert projected == {"titel": "T"}


def test_relation_target_ids_cover_top_level_and_group_children() -> None:
    group = _field("beteiligte", field_type="group")
    fields = [_field("schenker"), group, _field("person", parent_id=group.id)]
    stored = {"schenker": [_entry(PUBLIC)], "beteiligte": [{"person": _entry(DRAFT)}, {"other": 1}]}

    assert relation_target_ids(stored, fields) == {"entity": {PUBLIC, DRAFT}}


@pytest.mark.asyncio
async def test_load_hidden_relation_targets_keeps_only_public_ids_visible() -> None:
    result = MagicMock()
    result.scalars.return_value.all.return_value = [uuid.UUID(PUBLIC)]
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    stored = {"schenker": [_entry(PUBLIC), _entry(DRAFT), {"id": "kein-uuid", "label": "x"}]}

    hidden = await load_hidden_relation_targets(db, [stored], [_field("schenker")])

    assert hidden == {DRAFT, "kein-uuid"}
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_load_hidden_relation_targets_skips_the_query_without_relation_values() -> None:
    db = AsyncMock()

    assert await load_hidden_relation_targets(db, [{"titel": "T"}], [_field("schenker")]) == set()
    db.execute.assert_not_awaited()
