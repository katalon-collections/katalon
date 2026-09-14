# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Presence Lock: mode gating (issue #371)."""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from katalon.core.models import User
from katalon.services.presence_service import ActivePresence, enforce_not_blocked


def _mock_db(*, mode: str, others: list[ActivePresence]) -> AsyncMock:
    config = MagicMock()
    config.presence_lock_mode = mode
    joined_rows = [(MagicMock(user_id=p.user_id, last_seen_at=p.since), p.user_email) for p in others]
    execute_result = MagicMock()
    execute_result.all.return_value = joined_rows
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=config)
    db.execute = AsyncMock(return_value=execute_result)
    return db


def _user() -> User:
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    return user


@pytest.mark.asyncio
async def test_warning_mode_never_blocks() -> None:
    other = ActivePresence(user_id=uuid.uuid4(), user_email="a@example.com", since=None)
    db = _mock_db(mode="warning", others=[other])
    await enforce_not_blocked(db, "object", uuid.uuid4(), _user())


@pytest.mark.asyncio
async def test_blocking_mode_no_other_presence_passes() -> None:
    db = _mock_db(mode="blocking", others=[])
    await enforce_not_blocked(db, "object", uuid.uuid4(), _user())


@pytest.mark.asyncio
async def test_blocking_mode_with_other_presence_raises_409() -> None:
    other = ActivePresence(user_id=uuid.uuid4(), user_email="anna@example.com", since=None)
    db = _mock_db(mode="blocking", others=[other])
    with pytest.raises(HTTPException) as exc:
        await enforce_not_blocked(db, "object", uuid.uuid4(), _user())
    assert exc.value.status_code == 409
    assert exc.value.detail == {"error": "presence_locked", "locked_by": "anna@example.com"}
