# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Manual lock: tz-aware expires_at from the API must be stored as naive UTC."""
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from katalon.services.lock_service import set_lock


class _FakeResult:
    def one_or_none(self):
        return None

    def all(self):
        return []


class _FakeSession:
    def __init__(self):
        self.added = []

    async def execute(self, stmt):
        return _FakeResult()

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass


async def test_tz_aware_expires_at_is_stored_naive_utc():
    db = _FakeSession()
    user = SimpleNamespace(id=uuid.uuid4(), email="test@example.org")
    # ISO string with offset as sent by the admin UI (toISOString → "Z").
    aware = datetime(2026, 9, 10, 23, 59, 59, tzinfo=UTC)

    info = await set_lock(db, "object", uuid.uuid4(), user, expires_at=aware)

    lock = db.added[0]
    assert lock.expires_at.tzinfo is None
    assert lock.expires_at == aware.replace(tzinfo=None)
    assert info.expires_at == aware.replace(tzinfo=None)


async def test_naive_expires_at_passes_through():
    db = _FakeSession()
    user = SimpleNamespace(id=uuid.uuid4(), email="test@example.org")
    naive = datetime(2026, 9, 10, 23, 59, 59)

    await set_lock(db, "object", uuid.uuid4(), user, expires_at=naive)

    assert db.added[0].expires_at == naive


async def test_list_active_locks():
    from katalon.core.models import ResourceLock
    from katalon.services.lock_service import list_active_locks

    u_id = uuid.uuid4()
    o_id = uuid.uuid4()
    mock_lock = ResourceLock(
        resource_type="object",
        resource_id=o_id,
        locked_by=u_id,
        locked_at=datetime(2026, 10, 7, 10, 0, 0),
        reason="Katalogisierung",
    )

    class _MockResult:
        def all(self):
            return [(mock_lock, "curator@example.org")]

    class _MockResultEmpty:
        def all(self):
            return [(o_id, "OBJ-001", {"title": "Testgemälde"})]

    class _MockSession:
        def __init__(self):
            self.calls = 0

        async def execute(self, stmt):
            self.calls += 1
            if self.calls == 1:
                return _MockResult()
            return _MockResultEmpty()

    db = _MockSession()
    locks = await list_active_locks(db, user_id=u_id)
    assert len(locks) == 1
    assert locks[0].resource_type == "object"
    assert locks[0].resource_id == o_id
    assert locks[0].locked_by_email == "curator@example.org"
    assert locks[0].reason == "Katalogisierung"
    assert locks[0].idno == "OBJ-001"
    assert locks[0].title == "Testgemälde"

