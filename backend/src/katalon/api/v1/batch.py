# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from katalon.core.dependencies import CurrentUser, DBDep, has_record_permission
from katalon.core.schemas import BatchRequest, BatchResponse
from katalon.services.batch_service import apply_batch, get_model, resolve_record_ids
from katalon.workers.batch_tasks import batch_edit_task
from katalon.workers.enqueue import enqueue_or_503

router = APIRouter(prefix="/batch", tags=["batch"])

_ASYNC_THRESHOLD = 100


@router.post(
    "/{record_type}",
    response_model=BatchResponse,
    summary="Apply a batch operation to a set of records",
    responses={
        403: {"description": "Insufficient permissions"},
        422: {"description": "Invalid request or unknown record type"},
        503: {"description": "Background broker unavailable (async path)"},
    },
)
async def batch_edit(
    record_type: str,
    data: BatchRequest,
    db: DBDep,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Apply one batch operation to many records of a single type.

    The caller can either pass an explicit list of record IDs (`ids`) or the
    filters from the current list view (`filters`) to target all matching records
    across pages. Operations above the async threshold are handed to Celery and
    the endpoint returns a task id to poll.
    """
    try:
        get_model(record_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if not await has_record_permission(db, current_user, record_type, "update"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    batch_job_id = uuid.uuid4()
    record_ids = await resolve_record_ids(
        db,
        record_type,
        ids=data.ids,
        filters=data.filters,
    )

    if not record_ids:
        return BatchResponse(
            affected=0,
            errors=["Keine Datensätze für die Batch-Operation gefunden."],
            batch_job_id=batch_job_id,
        ).model_dump()

    can_edit_locked = current_user.role in {"admin", "superuser"}

    if len(record_ids) > _ASYNC_THRESHOLD:
        task_id = enqueue_or_503(
            batch_edit_task,
            record_type,
            data.model_dump(mode="json"),
            str(current_user.id) if current_user else None,
            str(batch_job_id),
        )
        return BatchResponse(
            affected=0,
            errors=[],
            batch_job_id=batch_job_id,
            task_id=task_id,
        ).model_dump()

    result = await apply_batch(
        db,
        record_type,
        record_ids,
        data.operation,
        current_user.id,
        batch_job_id,
        can_edit_locked=can_edit_locked,
    )
    await db.commit()
    return BatchResponse(
        affected=result["affected"],
        errors=result["errors"],
        batch_job_id=batch_job_id,
    ).model_dump()
