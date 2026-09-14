# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import pytest
from fastapi import HTTPException


class _PendingResult:
    state = "PENDING"
    info = None


class _Redis:
    def __init__(self, known: bool) -> None:
        self.known = known

    def exists(self, key: str) -> bool:
        return self.known


@pytest.mark.asyncio
async def test_task_status_rejects_unknown_pending_task(monkeypatch: pytest.MonkeyPatch) -> None:
    from celery import result as celery_result

    from katalon.api.v1 import importer

    monkeypatch.setattr(celery_result, "AsyncResult", lambda *args, **kwargs: _PendingResult())
    monkeypatch.setattr(importer, "_get_redis", lambda: _Redis(known=False))

    with pytest.raises(HTTPException, match="nicht gefunden") as exc:
        await importer.task_status("missing-task", current_user=object())

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_task_status_keeps_known_pending_task(monkeypatch: pytest.MonkeyPatch) -> None:
    from celery import result as celery_result

    from katalon.api.v1 import importer

    monkeypatch.setattr(celery_result, "AsyncResult", lambda *args, **kwargs: _PendingResult())
    monkeypatch.setattr(importer, "_get_redis", lambda: _Redis(known=True))

    assert await importer.task_status("queued-task", current_user=object()) == {"state": "PENDING"}
