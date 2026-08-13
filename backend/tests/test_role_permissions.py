from unittest.mock import AsyncMock, MagicMock

import pytest

from katalon.core.dependencies import has_record_permission
from katalon.core.models import User


@pytest.mark.asyncio
async def test_admin_always_has_record_permissions() -> None:
    db = AsyncMock()
    user = User(email="admin@example.org", hashed_password="x", role="admin")

    assert await has_record_permission(db, user, "object", "delete") is True
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_configured_record_permission_is_required() -> None:
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    user = User(email="viewer@example.org", hashed_password="x", role="viewer")

    assert await has_record_permission(db, user, "object", "read") is False
    result.scalar_one_or_none.return_value = object()
    assert await has_record_permission(db, user, "object", "read") is True
