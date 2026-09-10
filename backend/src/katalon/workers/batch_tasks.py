# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Coroutine
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from katalon.config import settings
from katalon.workers.celery_app import celery_app
from katalon.workers.email_tasks import send_user_email
from katalon.workers.enqueue import enqueue

logger = logging.getLogger(__name__)


def _run[T](coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)


def _make_session() -> tuple[async_sessionmaker[AsyncSession], AsyncEngine]:
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False), engine


def _queue_batch_notification(user_id: str | None, record_type: str, result: dict[str, Any]) -> None:
    if not user_id:
        return
    if result["errors"] and result["affected"] == 0:
        subject = "Katalon: Batch-Bearbeitung fehlgeschlagen"
        text = f"Die Batch-Bearbeitung von {record_type}-Datensätzen konnte nicht ausgeführt werden."
    else:
        subject = "Katalon: Batch-Bearbeitung abgeschlossen"
        text = (
            f"Die Batch-Bearbeitung von {record_type}-Datensätzen ist abgeschlossen.\n\n"
            f"Geändert: {result['affected']}\nFehler: {len(result['errors'])}"
        )
    enqueue(send_user_email, user_id, subject, text)


@celery_app.task(name="katalon.batch_edit", bind=True)
def batch_edit_task(
    self: Any,
    record_type: str,
    request_dict: dict[str, Any],
    user_id: str | None,
    batch_job_id: str,
) -> dict[str, Any]:
    """Run a batch edit asynchronously for large sets of records."""
    from katalon.core.schemas import BatchRequest
    from katalon.services.batch_service import apply_batch, resolve_record_ids

    AsyncSessionLocal, engine = _make_session()

    request = BatchRequest.model_validate(request_dict)
    operation = request.operation
    user_uuid = uuid.UUID(user_id) if user_id else None
    batch_uuid = uuid.UUID(batch_job_id)

    async def _do() -> dict[str, Any]:
        async with AsyncSessionLocal() as session:
            record_ids = await resolve_record_ids(
                session,
                record_type,
                ids=request.ids,
                filters=request.filters,
            )
            total = len(record_ids)
            self.update_state(
                state="STARTED",
                meta={"current": 0, "total": total, "stage": "resolving"},
            )

            result = await apply_batch(
                session,
                record_type,
                record_ids,
                operation,
                user_uuid,
                batch_uuid,
                can_edit_locked=user_uuid is not None,  # task context is less strict; lock via permissions already enforced
            )
            await session.commit()
            self.update_state(
                state="SUCCESS",
                meta={"current": result["affected"], "total": total, "stage": "done"},
            )
            return {
                "affected": result["affected"],
                "errors": result["errors"],
                "batch_job_id": batch_job_id,
                "record_type": record_type,
            }

    try:
        result = _run(_do())
    except Exception as exc:
        logger.exception("Async batch edit failed for %s/%s", record_type, batch_job_id)
        result = {
            "affected": 0,
            "errors": [f"Async batch edit failed: {exc}"],
            "batch_job_id": batch_job_id,
            "record_type": record_type,
        }
    finally:
        _run(engine.dispose())
    _queue_batch_notification(user_id, record_type, result)
    return result
