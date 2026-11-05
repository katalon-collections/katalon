# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""
Rebuild the schema-derived relation rows of all records.

Usage:
    katalon-manage resync-schema-relations --dry-run
    katalon-manage resync-schema-relations

Older versions mirrored relation fields without looking at the record's subtype, so equally
named fields of different subtypes created identical rows. The dry run only reports them.
The real run deletes and recreates the schema-derived rows of every record (a data change:
run it on an instance only with the operator's approval, after a backup). It does not
reindex: afterwards run a full reindex if relations feed search facets.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

BATCH_SIZE = 200


@dataclass
class ResyncReport:
    duplicate_groups: int  # before the run
    extra_rows: int  # before the run
    records: int
    resynced: int
    extra_rows_after: int | None = None  # None in a dry run


async def count_duplicates(session: Any) -> tuple[int, int]:
    """(groups with more than one identical schema-derived row, surplus rows)."""
    from sqlalchemy import func, select

    from katalon.core.models import Relation

    source_field = Relation.metadata_["source_field"].astext
    groups = (
        select(func.count().label("n"))
        .where(Relation.is_schema_derived.is_(True))
        .group_by(
            Relation.from_type,
            Relation.from_id,
            Relation.to_type,
            Relation.to_id,
            Relation.relation_type,
            source_field,
        )
        .having(func.count() > 1)
        .subquery()
    )
    row = (
        await session.execute(
            select(func.count(), func.coalesce(func.sum(groups.c.n - 1), 0)).select_from(groups)
        )
    ).one()
    return int(row[0]), int(row[1])


async def resync(session_factory: Callable[[], Any], *, dry_run: bool) -> ResyncReport:
    from sqlalchemy import select

    from katalon.services.relation_service import _RECORD_MODELS, sync_schema_relations

    async with session_factory() as session:
        groups, extra = await count_duplicates(session)
        records = 0
        resynced = 0
        for record_type, model in _RECORD_MODELS.items():
            query = select(model).order_by(model.id)
            if hasattr(model, "deleted_at"):
                query = query.where(model.deleted_at.is_(None))
            offset = 0
            while True:
                batch = (await session.execute(query.limit(BATCH_SIZE).offset(offset))).scalars().all()
                if not batch:
                    break
                for record in batch:
                    records += 1
                    if not dry_run:
                        await sync_schema_relations(
                            session, record_type, record.id, record.metadata_ or {}
                        )
                        resynced += 1
                if not dry_run:
                    await session.commit()
                offset += BATCH_SIZE
        if not dry_run:
            _, extra_after = await count_duplicates(session)
            return ResyncReport(groups, extra, records, resynced, extra_after)
    return ResyncReport(groups, extra, records, resynced)


def run(dry_run: bool) -> ResyncReport:
    from katalon.database import AsyncSessionLocal

    return asyncio.run(resync(AsyncSessionLocal, dry_run=dry_run))
