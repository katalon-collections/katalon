# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from katalon.config import settings
from katalon.core.visibility import PUBLIC_STATUSES
from katalon.integrations.jsonld_format import record_uri_path
from katalon.integrations.oxigraph import OxigraphClient, get_oxigraph_client
from katalon.services.rdf_service import (
    RECORD_MODEL_MAP,
    export_single_record,
    get_canonical_base_url,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def get_record_graph_uri(
    record_type: str,
    record_id: str | uuid.UUID,
    base_url: str | None = None,
) -> str:
    """Compute the canonical named graph URI for a record."""
    norm_type = record_type.lower().strip()
    if norm_type.endswith("s") and norm_type[:-1] in RECORD_MODEL_MAP:
        norm_type = norm_type[:-1]

    resolved_base = base_url if base_url is not None else get_canonical_base_url()
    return record_uri_path(norm_type, str(record_id), base_url=resolved_base)


def is_record_publicly_visible(record: Any) -> bool:
    """Check whether a record meets the criteria for public visibility in the triple store."""
    if getattr(record, "deleted_at", None) is not None:
        return False
    status = getattr(record, "status", None)
    return not (status is not None and status not in PUBLIC_STATUSES)


async def sync_record_to_oxigraph(
    record_type: str,
    record_id: str | uuid.UUID,
    db: AsyncSession,
    oxigraph_client: OxigraphClient | None = None,
) -> dict[str, Any]:
    """Synchronize a single record's named graph to Oxigraph.

    - If public: exports Turtle and stores it in Oxigraph (`PUT /store?graph=...`).
    - If unpublished or deleted: drops the named graph from Oxigraph (`DELETE /store?graph=...`).
    - If oxigraph is disabled: returns skipped.
    """
    if not settings.oxigraph_enabled:
        return {"status": "skipped", "reason": "disabled"}

    norm_type = record_type.lower().strip()
    if norm_type.endswith("s") and norm_type[:-1] in RECORD_MODEL_MAP:
        norm_type = norm_type[:-1]

    if norm_type not in RECORD_MODEL_MAP:
        return {"status": "error", "error": f"Unknown record type: {record_type}"}

    uid = record_id if isinstance(record_id, uuid.UUID) else uuid.UUID(str(record_id))
    graph_uri = get_record_graph_uri(norm_type, uid)

    model, _ = RECORD_MODEL_MAP[norm_type]
    stmt = select(model).where(model.id == uid)
    record = (await db.execute(stmt)).scalar_one_or_none()

    client = oxigraph_client or get_oxigraph_client()
    should_close = oxigraph_client is None

    try:
        if record is None or not is_record_publicly_visible(record):
            # Record is missing, deleted or not published -> remove named graph
            deleted = await client.delete_graph(graph_uri)
            return {"status": "deleted", "graph_uri": graph_uri, "existed": deleted}

        # Record is publicly visible -> generate Turtle and update named graph
        base_url = get_canonical_base_url()
        turtle_data, _, _ = await export_single_record(
            db, norm_type, uid, format="turtle", base_url=base_url
        )
        await client.put_graph(graph_uri, turtle_data, content_type="text/turtle")
        return {"status": "synced", "graph_uri": graph_uri}
    finally:
        if should_close:
            await client.close()


async def remove_record_from_oxigraph(
    record_type: str,
    record_id: str | uuid.UUID,
    oxigraph_client: OxigraphClient | None = None,
) -> dict[str, Any]:
    """Remove a record's named graph from Oxigraph."""
    if not settings.oxigraph_enabled:
        return {"status": "skipped", "reason": "disabled"}

    graph_uri = get_record_graph_uri(record_type, record_id)
    client = oxigraph_client or get_oxigraph_client()
    should_close = oxigraph_client is None

    try:
        deleted = await client.delete_graph(graph_uri)
        return {"status": "deleted", "graph_uri": graph_uri, "existed": deleted}
    finally:
        if should_close:
            await client.close()


async def rebuild_all_oxigraph(
    db: AsyncSession,
    oxigraph_client: OxigraphClient | None = None,
    batch_size: int = 100,
) -> dict[str, Any]:
    """Rebuild all named graphs in Oxigraph for all published records."""
    if not settings.oxigraph_enabled:
        return {"status": "skipped", "reason": "disabled"}

    client = oxigraph_client or get_oxigraph_client()
    should_close = oxigraph_client is None
    stats: dict[str, int] = dict.fromkeys(RECORD_MODEL_MAP, 0)
    total_synced = 0

    try:
        for rtype, (model, _) in RECORD_MODEL_MAP.items():
            query = select(model.id)
            if hasattr(model, "deleted_at"):
                query = query.where(model.deleted_at.is_(None))
            if hasattr(model, "status"):
                query = query.where(model.status.in_(PUBLIC_STATUSES))

            result = await db.execute(query)
            record_ids = result.scalars().all()

            for rec_id in record_ids:
                try:
                    res = await sync_record_to_oxigraph(rtype, rec_id, db, oxigraph_client=client)
                    if res.get("status") == "synced":
                        stats[rtype] += 1
                        total_synced += 1
                except Exception as exc:
                    logger.error("Failed to sync %s %s to Oxigraph during rebuild: %s", rtype, rec_id, exc)

        return {"status": "completed", "total_synced": total_synced, "details": stats}
    finally:
        if should_close:
            await client.close()
