# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.dependencies import get_user_features
from katalon.core.models import (
    AuditLog,
    Object,
    Procedure,
    User,
)
from katalon.core.schemas import LockRead
from katalon.core.visibility import readable_record_types
from katalon.services import working_set_service
from katalon.services.audit_service import resolve_record_labels
from katalon.services.lock_service import list_active_locks
from katalon.services.search_service import _extract_title


class DashboardRecentItem(BaseModel):
    record_type: str
    record_id: uuid.UUID
    record_label: str
    action: str
    created_at: datetime


class DashboardWorkingSet(BaseModel):
    id: uuid.UUID
    name: str
    record_type: str | None = None
    item_count: int = 0
    updated_at: datetime


class DashboardProcedure(BaseModel):
    id: uuid.UUID
    idno: str | None = None
    reference_number: str | None = None
    title: str
    procedure_type: str
    due_date: str | None = None
    days_left: int | None = None


class DashboardAuditItem(BaseModel):
    record_type: str
    record_id: uuid.UUID
    record_label: str
    user_name: str
    action: str
    created_at: datetime


class DashboardSummary(BaseModel):
    recents: list[DashboardRecentItem]
    my_locks: list[LockRead]
    all_locks: list[LockRead] | None = None
    working_sets: list[DashboardWorkingSet]
    due_procedures: list[DashboardProcedure]
    team_activity: list[DashboardAuditItem]
    draft_counts: dict[str, int]


async def get_dashboard_summary(
    db: AsyncSession,
    current_user: User,
) -> DashboardSummary:
    readable_types = await readable_record_types(db, current_user)
    features = await get_user_features(db, current_user)
    is_admin = current_user.role in ("admin", "superuser")

    # 1. Recents: recent AuditLog entries for current_user
    recent_query = (
        select(AuditLog)
        .where(AuditLog.user_id == current_user.id)
        .order_by(AuditLog.created_at.desc())
        .limit(30)
    )
    res = await db.execute(recent_query)
    raw_logs = res.scalars().all()

    seen_records: set[tuple[str, uuid.UUID]] = set()
    filtered_logs: list[AuditLog] = []
    for log in raw_logs:
        if readable_types is not None and log.record_type not in readable_types:
            continue
        key = (log.record_type, log.record_id)
        if key not in seen_records:
            seen_records.add(key)
            filtered_logs.append(log)
            if len(filtered_logs) >= 8:
                break

    resolved_labels = await resolve_record_labels(
        db, [(entry.record_type, entry.record_id) for entry in filtered_logs]
    )
    recents = [
        DashboardRecentItem(
            record_type=entry.record_type,
            record_id=entry.record_id,
            record_label=resolved_labels.get(entry.record_id) or str(entry.record_id)[:8],
            action=entry.action,
            created_at=entry.created_at,
        )
        for entry in filtered_logs
    ]

    # 2. My Locks
    my_locks_raw = await list_active_locks(db, user_id=current_user.id)
    my_locks = [
        LockRead(
            resource_type=lock_info.resource_type,
            resource_id=str(lock_info.resource_id) if lock_info.resource_id else "",
            locked_by=str(lock_info.locked_by),
            locked_by_email=lock_info.locked_by_email,
            locked_at=lock_info.locked_at,
            expires_at=lock_info.expires_at,
            reason=lock_info.reason,
            title=lock_info.title,
            idno=lock_info.idno,
        )
        for lock_info in my_locks_raw
    ]

    # 3. All Locks (for admin or users with manual_lock feature)
    all_locks: list[LockRead] | None = None
    if is_admin or "manual_lock" in features:
        all_raw = await list_active_locks(db)
        all_locks = [
            LockRead(
                resource_type=lock_info.resource_type,
                resource_id=str(lock_info.resource_id) if lock_info.resource_id else "",
                locked_by=str(lock_info.locked_by),
                locked_by_email=lock_info.locked_by_email,
                locked_at=lock_info.locked_at,
                expires_at=lock_info.expires_at,
                reason=lock_info.reason,
                title=lock_info.title,
                idno=lock_info.idno,
            )
            for lock_info in all_raw[:15]
        ]

    # 4. Working sets (if feature enabled)
    working_sets: list[DashboardWorkingSet] = []
    if is_admin or "working_sets" in features:
        sets = await working_set_service.list_working_sets(db, current_user)
        working_sets = [
            DashboardWorkingSet(
                id=s.id,
                name=s.name,
                record_type=s.record_type,
                item_count=s.item_count,
                updated_at=s.updated_at,
            )
            for s in sets[:5]
        ]

    # 5. Due procedures (if readable)
    due_procedures: list[DashboardProcedure] = []
    can_read_procedures = readable_types is None or "procedure" in readable_types
    if can_read_procedures:
        today = date.today()
        max_due = today + timedelta(days=60)
        proc_query = (
            select(Procedure)
            .where(
                Procedure.status == "active",
                Procedure.due_date.is_not(None),
                Procedure.due_date <= max_due,
            )
            .order_by(Procedure.due_date.asc())
            .limit(5)
        )
        proc_res = await db.execute(proc_query)
        procs = proc_res.scalars().all()
        for p in procs:
            p_md = getattr(p, "metadata_", None) or {}
            p_title = _extract_title(p_md) or p.reference_number or p.idno or str(p.id)[:8]
            days_left = (p.due_date - today).days if p.due_date else None
            due_procedures.append(
                DashboardProcedure(
                    id=p.id,
                    idno=p.idno,
                    reference_number=p.reference_number,
                    title=p_title,
                    procedure_type=p.procedure_type,
                    due_date=p.due_date.isoformat() if p.due_date else None,
                    days_left=days_left,
                )
            )

    # 6. Team activity (if audit_log feature enabled)
    team_activity: list[DashboardAuditItem] = []
    if is_admin or "audit_log" in features:
        team_query = (
            select(AuditLog, User.email)
            .outerjoin(User, AuditLog.user_id == User.id)
            .order_by(AuditLog.created_at.desc())
            .limit(10)
        )
        team_res = await db.execute(team_query)
        team_rows = team_res.all()
        t_refs = [(log.record_type, log.record_id) for log, _ in team_rows]
        t_labels = await resolve_record_labels(db, t_refs)
        for log, email in team_rows:
            if readable_types is not None and log.record_type not in readable_types:
                continue
            lbl = t_labels.get(log.record_id) or str(log.record_id)[:8]
            u_name = email.split("@")[0] if email else "System"
            team_activity.append(
                DashboardAuditItem(
                    record_type=log.record_type,
                    record_id=log.record_id,
                    record_label=lbl,
                    user_name=u_name,
                    action=log.action,
                    created_at=log.created_at,
                )
            )

    # 7. Draft counts
    draft_counts: dict[str, int] = {}
    if readable_types is None or "object" in readable_types:
        obj_draft_res = await db.execute(
            select(func.count(Object.id)).where(
                Object.status == "draft",
                Object.deleted_at.is_(None),
            )
        )
        draft_counts["object"] = obj_draft_res.scalar_one() or 0
    if can_read_procedures:
        proc_draft_res = await db.execute(
            select(func.count(Procedure.id)).where(Procedure.status == "draft")
        )
        draft_counts["procedure"] = proc_draft_res.scalar_one() or 0

    return DashboardSummary(
        recents=recents,
        my_locks=my_locks,
        all_locks=all_locks,
        working_sets=working_sets,
        due_procedures=due_procedures,
        team_activity=team_activity,
        draft_counts=draft_counts,
    )
