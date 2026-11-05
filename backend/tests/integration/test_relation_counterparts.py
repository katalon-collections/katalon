# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid

import pytest

from katalon.core.models import FieldDefinition
from katalon.services.schema_service import find_counter_direction_relation_fields


def _relation(
    name: str,
    owner: tuple[str, str | None],
    target: tuple[str, str | None],
    *,
    deleted: bool = False,
    parent_id: uuid.UUID | None = None,
) -> FieldDefinition:
    settings: dict[str, str] = {"target_type": target[0]}
    if target[1]:
        settings["target_subtype"] = target[1]
    return FieldDefinition(
        target_type=owner[0],
        target_subtype=owner[1],
        name=name,
        label={"de": name},
        field_type="relation",
        is_deleted=deleted,
        parent_id=parent_id,
        settings=settings,
    )


async def _find(session, owner, target, exclude=None) -> set[uuid.UUID]:
    found = await find_counter_direction_relation_fields(
        session,
        owner_type=owner[0],
        owner_subtype=owner[1],
        target_type=target[0],
        target_subtype=target[1],
        exclude_field_id=exclude,
    )
    return {f.id for f in found}


@pytest.mark.asyncio
async def test_counter_direction_rules(app) -> None:
    from katalon.database import AsyncSessionLocal

    s = uuid.uuid4().hex[:8]
    expr, work = f"expr_{s}", f"work_{s}"
    async with AsyncSessionLocal() as session:
        a = _relation(f"zugehoeriges_werk_{s}", ("occurrence", expr), ("occurrence", work))
        b = _relation(f"expression_{s}", ("occurrence", work), ("occurrence", expr))
        session.add_all([a, b])
        await session.flush()

        # work -> expression finds expression -> work, and the other way round
        assert b.id in await _find(session, ("occurrence", expr), ("occurrence", work))
        assert a.id in await _find(session, ("occurrence", work), ("occurrence", expr))
        # the field itself is never its own candidate
        assert b.id not in await _find(
            session, ("occurrence", expr), ("occurrence", work), exclude=b.id
        )

        # same direction: expression -> work does not collide with expression -> work
        assert a.id not in await _find(session, ("occurrence", expr), ("occurrence", work))
        # a different subtype pair does not match
        assert not {a.id, b.id} & await _find(
            session, ("occurrence", f"x_{s}"), ("occurrence", f"y_{s}")
        )

        # NULL subtype on the planned field matches every subtype of the existing one
        assert b.id in await _find(session, ("occurrence", None), ("occurrence", work))
        assert b.id in await _find(session, ("occurrence", expr), ("occurrence", None))
        await session.rollback()


@pytest.mark.asyncio
async def test_counter_direction_ignores_null_existing_subtypes_deleted_and_other_targets(app) -> None:
    from katalon.database import AsyncSessionLocal

    s = uuid.uuid4().hex[:8]
    sub = f"sub_{s}"
    async with AsyncSessionLocal() as session:
        generic = _relation(f"generic_{s}", ("entity", None), ("object", None))
        deleted = _relation(f"deleted_{s}", ("entity", sub), ("object", sub), deleted=True)
        elsewhere = _relation(f"elsewhere_{s}", ("entity", sub), ("place", sub))
        session.add_all([generic, deleted, elsewhere])
        await session.flush()

        # object -> entity: the entity -> object field with NULL subtypes matches
        found = await _find(session, ("object", sub), ("entity", sub))
        assert generic.id in found
        assert deleted.id not in found
        # entity -> place is not the opposite of object -> entity
        assert elsewhere.id not in found
        await session.rollback()


@pytest.mark.asyncio
async def test_counter_direction_counts_group_sub_fields(app) -> None:
    from katalon.database import AsyncSessionLocal

    s = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        group = FieldDefinition(
            target_type="entity", target_subtype=f"g_{s}", name=f"gruppe_{s}",
            label={"de": "Gruppe"}, field_type="group", settings={},
        )
        session.add(group)
        await session.flush()
        child = _relation(
            f"kind_{s}", ("entity", f"g_{s}"), ("object", f"o_{s}"), parent_id=group.id
        )
        session.add(child)
        await session.flush()
        assert child.id in await _find(session, ("object", f"o_{s}"), ("entity", f"g_{s}"))
        await session.rollback()


@pytest.mark.asyncio
async def test_relation_counterparts_endpoint_returns_candidate_details(
    app, async_client, auth_headers
) -> None:
    from katalon.database import AsyncSessionLocal

    s = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as session:
        b = _relation(f"expression_{s}", ("occurrence", f"work_{s}"), ("occurrence", f"expr_{s}"))
        session.add(b)
        await session.commit()

    response = await async_client.post(
        "/v1/schema/relation-counterparts",
        headers=auth_headers,
        json={
            "target_type": "occurrence",
            "target_subtype": f"expr_{s}",
            "relation_target_type": "occurrence",
            "relation_target_subtype": f"work_{s}",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json() == [
        {
            "id": str(b.id),
            "name": f"expression_{s}",
            "label": {"de": f"expression_{s}"},
            "target_subtype": f"work_{s}",
            "relation_target_subtype": f"expr_{s}",
            "parent_name": None,
        }
    ]
