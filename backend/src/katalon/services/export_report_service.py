# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Record-level export report: which public records a mapping set would reject, and why.

Lets an institution see an aggregator's feedback ("42 records lack ...") before a
delivery instead of after it.
"""

from __future__ import annotations

import re
import uuid
from collections import Counter
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.visibility import PUBLIC_STATUSES
from katalon.services import export_context_service, metadata_format_service
from katalon.services.metadata_mapping_service import compile_mapping_set, get_mapping_set


@dataclass
class RecordProblem:
    rec_id: str  # lidoRecID-style identifier (ISIL--idno) when an ISIL is configured
    record_id: str
    messages: list[str]


@dataclass
class ExportReport:
    checked: int = 0
    problems: list[RecordProblem] = field(default_factory=list)

    def counts(self) -> Counter[str]:
        """Number of records per problem kind (message without the per-record detail)."""
        return Counter(
            kind
            for problem in self.problems
            for kind in dict.fromkeys(
                re.sub(r" \([^()]*\)$", "", message).split(": ", 1)[0] for message in problem.messages
            )
        )


async def _public_record_ids(db: AsyncSession, record_type: str) -> AsyncIterator[uuid.UUID]:
    model = export_context_service._MODEL_MAP[record_type]
    result = await db.stream_scalars(
        select(model.id)
        .where(model.status.in_(PUBLIC_STATUSES), model.deleted_at.is_(None))
        .order_by(model.id)
    )
    async for record_id in result:
        yield record_id


async def build_report(db: AsyncSession, set_id: uuid.UUID) -> ExportReport:
    mapping_set = await get_mapping_set(db, set_id)
    if mapping_set is None:
        raise ValueError("ExportMappingSet nicht gefunden.")
    fmt = await metadata_format_service.get_format(mapping_set.format_key)
    if fmt is None:
        raise ValueError(f"Unbekanntes Format '{mapping_set.format_key}'.")
    if mapping_set.record_type not in export_context_service._MODEL_MAP:
        raise ValueError(f"Nicht unterstützter Datensatztyp: {mapping_set.record_type}")

    compiled = compile_mapping_set(mapping_set)
    isil = str(compiled.institution_config.get("isil") or "").strip()
    via_types = await export_context_service.collect_via_relation_types(db, extra_rules=compiled.rules)
    report = ExportReport()
    ids = [record_id async for record_id in _public_record_ids(db, mapping_set.record_type)]
    for record_id in ids:
        ctx = await export_context_service.build_export_context_from_db(
            db, mapping_set.record_type, record_id, via_relation_types=via_types
        )
        report.checked += 1
        if mapping_set.target_subtype and ctx.record.target_subtype != mapping_set.target_subtype:
            continue
        messages = fmt.required_field_errors(ctx, compiled)
        if messages:
            idno = ctx.record.idno or ctx.record.id
            report.problems.append(
                RecordProblem(
                    rec_id=f"{isil}--{idno}" if isil else idno,
                    record_id=ctx.record.id,
                    messages=messages,
                )
            )
        db.expunge_all()  # keep the session small on large collections
    return report
