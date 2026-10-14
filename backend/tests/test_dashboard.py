# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Unit tests for dashboard service and schemas."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from katalon.services.dashboard_service import (
    DashboardAuditItem,
    DashboardProcedure,
    DashboardRecentItem,
    DashboardSummary,
    DashboardWorkingSet,
    get_dashboard_summary,
)


def test_dashboard_schemas() -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    rec = DashboardRecentItem(
        record_type="object",
        record_id=uuid.uuid4(),
        record_label="Altarbild (OBJ-1)",
        action="update",
        created_at=now,
    )
    assert rec.record_type == "object"
    assert rec.action == "update"

    ws = DashboardWorkingSet(
        id=uuid.uuid4(),
        name="Sommerausstellung",
        record_type="object",
        item_count=12,
        updated_at=now,
    )
    assert ws.item_count == 12

    proc = DashboardProcedure(
        id=uuid.uuid4(),
        title="Leihgabe an Kunstmuseum",
        procedure_type="loan_out",
        due_date="2026-11-01",
        days_left=25,
    )
    assert proc.days_left == 25

    audit_it = DashboardAuditItem(
        record_type="entity",
        record_id=uuid.uuid4(),
        record_label="Albrecht Dürer",
        user_name="curator",
        action="create",
        created_at=now,
    )
    assert audit_it.user_name == "curator"

    summary = DashboardSummary(
        recents=[rec],
        my_locks=[],
        all_locks=None,
        working_sets=[ws],
        due_procedures=[proc],
        team_activity=[audit_it],
        draft_counts={"object": 5},
    )
    assert len(summary.recents) == 1
    assert summary.draft_counts["object"] == 5


async def test_get_dashboard_summary_mock() -> None:
    class _MockResult:
        def __init__(self, items=None, scalar=0):
            self._items = items or []
            self._scalar = scalar

        def scalars(self):
            return SimpleNamespace(all=lambda: self._items)

        def scalar_one(self):
            return self._scalar

        def all(self):
            return self._items

    class _MockSession:
        async def execute(self, stmt):
            return _MockResult(items=[], scalar=0)

    user = SimpleNamespace(
        id=uuid.uuid4(),
        email="admin@example.org",
        role="admin",
        features=["working_sets", "audit_log", "manual_lock"],
    )
    db = _MockSession()
    summary = await get_dashboard_summary(db, user)  # type: ignore[arg-type]
    assert isinstance(summary, DashboardSummary)
    assert summary.recents == []
    assert summary.my_locks == []
