# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid
from datetime import datetime

from fastapi import APIRouter, Query
from sqlalchemy import Text, and_, cast, exists, func, literal, or_, select, union_all

from katalon.core.dependencies import DBDep
from katalon.core.models import (
    AuditLog,
    Collection,
    Entity,
    Object,
    Occurrence,
    Place,
    Procedure,
    StorageLocation,
    User,
)
from katalon.core.schemas import AuditLogRead, Page
from katalon.services.audit_service import collapse_value, extract_title, format_label

router = APIRouter(prefix="/audit", tags=["audit"])


def _record_search_refs(query: str):
    """Return live records whose identifier or metadata contains ``query``."""
    def match(model):
        return model.idno.icontains(query, autoescape=True) | cast(model.metadata_, Text).icontains(
            query, autoescape=True
        )

    selects = [
        select(literal(record_type).label("record_type"), model.id.label("record_id")).where(match(model))
        for record_type, model in (
            ("object", Object),
            ("entity", Entity),
            ("place", Place),
            ("occurrence", Occurrence),
            ("collection", Collection),
            ("storage_location", StorageLocation),
        )
    ]
    selects.append(
        select(literal("procedure").label("record_type"), Procedure.id.label("record_id")).where(
            match(Procedure) | Procedure.reference_number.icontains(query, autoescape=True)
        )
    )
    return union_all(*selects).subquery()


def _filter_query(
    query,
    *,
    record_type: str | None = None,
    record_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    action: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    group_actions: bool = False,
):
    if record_type:
        query = query.where(AuditLog.record_type == record_type)
    if record_id:
        query = query.where(AuditLog.record_id == record_id)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    if action:
        query = query.where(
            AuditLog.action.startswith(f"{action}_")
            if group_actions and action in {"media", "relation"}
            else AuditLog.action == action
        )
    if created_from:
        query = query.where(AuditLog.created_at >= created_from)
    if created_to:
        query = query.where(AuditLog.created_at <= created_to)
    return query


def _related_uuid(value: object) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    if not isinstance(value, str):
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


async def _resolve_record_labels(db: DBDep, refs: list[tuple[str, uuid.UUID]]) -> dict[uuid.UUID, str]:
    """Fetch display labels ("title (idno)") for (record_type, record_id) pairs."""
    by_type: dict[str, list[uuid.UUID]] = {}
    for record_type, record_id in refs:
        by_type.setdefault(record_type, []).append(record_id)

    labels: dict[uuid.UUID, str] = {}

    for record_type, model in (
        ("object", Object),
        ("entity", Entity),
        ("place", Place),
        ("occurrence", Occurrence),
        ("collection", Collection),
        ("storage_location", StorageLocation),
    ):
        if record_type not in by_type:
            continue
        result = await db.execute(select(model.id, model.idno, model.metadata_).where(model.id.in_(by_type[record_type])))
        for id_, idno, md in result.all():
            labels[id_] = format_label(extract_title(md), idno, str(id_)[:8])

    if "procedure" in by_type:
        result = await db.execute(select(Procedure.id, Procedure.idno, Procedure.reference_number).where(Procedure.id.in_(by_type["procedure"])))
        for id_, idno, reference_number in result.all():
            labels[id_] = idno or reference_number or str(id_)[:8]

    return labels


def _delete_snapshot_label(log: AuditLog) -> str | None:
    """For a "delete" entry, the record row is already gone — build the label
    from the idno/title snapshotted into changed_fields at delete time instead
    of a (necessarily empty) live lookup."""
    if log.action != "delete":
        return None
    fields = log.changed_fields or {}
    idno, title = fields.get("idno"), fields.get("title")
    if not idno and not title:
        return None
    return format_label(title, idno, str(log.record_id)[:8])


def _collapse_diff_values(changed_fields: dict[str, object] | None) -> dict[str, object] | None:
    """Replace vocab-ish diff values (fresh dicts or legacy JSON strings) with
    their human-readable label so old audit entries don't leak the internal
    record id that was stringified into the snapshot at log time."""
    if not changed_fields:
        return changed_fields
    collapsed = dict(changed_fields)
    for side in ("old", "new"):
        current = collapsed.get(side)
        if not isinstance(current, dict):
            continue
        reduced: dict[str, object] = {}
        for key, value in current.items():
            label = collapse_value(value)
            reduced[key] = label if label is not None else value
        collapsed[side] = reduced
    return collapsed


@router.get(
    "",
    response_model=list[AuditLogRead],
    summary="List audit log entries with optional filters by type, record, user, and action",
)
async def list_audit_log(
    db: DBDep,
    record_type: str | None = None,
    record_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    action: str | None = None,
    limit: int = Query(100, ge=1, le=500),
) -> list[AuditLogRead]:
    query = select(AuditLog, User.email).outerjoin(User, AuditLog.user_id == User.id).order_by(AuditLog.created_at.desc()).limit(limit)
    query = _filter_query(
        query, record_type=record_type, record_id=record_id, user_id=user_id, action=action
    )

    result = await db.execute(query)
    rows = result.all()
    logs = [log for log, _ in rows]

    refs = {(log.record_type, log.record_id) for log in logs}
    for log in logs:
        related_type = (log.changed_fields or {}).get("related_record_type")
        related_id = (log.changed_fields or {}).get("related_record_id")
        related_uuid = _related_uuid(related_id)
        if isinstance(related_type, str) and related_uuid:
            refs.add((related_type, related_uuid))
    labels = await _resolve_record_labels(db, list(refs))

    out: list[AuditLogRead] = []
    for log, user_email in rows:
        changed_fields = _collapse_diff_values(log.changed_fields)
        related_id = (changed_fields or {}).get("related_record_id")
        related_uuid = _related_uuid(related_id)
        if related_uuid is not None and related_uuid in labels:
            changed_fields = {
                **(changed_fields or {}), "related_record_label": labels[related_uuid],
            }
        out.append(AuditLogRead(
            id=log.id,
            record_type=log.record_type,
            record_id=log.record_id,
            record_label=_delete_snapshot_label(log) or labels.get(log.record_id, str(log.record_id)[:8]),
            user_id=log.user_id,
            user_name=user_email or (str(log.user_id)[:8] if log.user_id else None),
            action=log.action,
            changed_fields=changed_fields,
            created_at=log.created_at,
        ))
    return out


@router.get(
    "/search",
    response_model=Page,
    summary="Search paginated audit log entries by record, user, action, and date",
)
async def search_audit_log(
    db: DBDep,
    q: str | None = Query(None, max_length=200),
    record_type: str | None = None,
    record_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    action: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> Page:
    """Search the global audit log without limiting the result set in the UI."""
    query = _filter_query(
        select(AuditLog, User.email).outerjoin(User, AuditLog.user_id == User.id),
        record_type=record_type,
        record_id=record_id,
        user_id=user_id,
        action=action,
        created_from=created_from,
        created_to=created_to,
        group_actions=True,
    )
    search_term = q.strip() if q else ""
    if search_term:
        # ponytail: substring matching reuses the record-list query shape; add dedicated indexes only if
        # EXPLAIN shows the migrated production corpus needs them.
        records = _record_search_refs(search_term)
        record_match = exists(
            select(records.c.record_id).where(
                and_(
                    records.c.record_type == AuditLog.record_type,
                    records.c.record_id == AuditLog.record_id,
                )
            )
        )
        query = query.where(
            or_(
                record_match,
                AuditLog.action.icontains(search_term, autoescape=True),
                User.email.icontains(search_term, autoescape=True),
                cast(AuditLog.changed_fields, Text).icontains(search_term, autoescape=True),
                cast(AuditLog.record_id, Text).icontains(search_term, autoescape=True),
            )
        )

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    # ponytail: offset pagination is sufficient for the audit UI; move to cursor pagination if deep pages are slow.
    rows = (
        await db.execute(
            query.order_by(AuditLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    logs = [log for log, _ in rows]
    refs = {(log.record_type, log.record_id) for log in logs}
    for log in logs:
        related_type = (log.changed_fields or {}).get("related_record_type")
        related_id = (log.changed_fields or {}).get("related_record_id")
        related_uuid = _related_uuid(related_id)
        if isinstance(related_type, str) and related_uuid:
            refs.add((related_type, related_uuid))
    labels = await _resolve_record_labels(db, list(refs))

    items: list[AuditLogRead] = []
    for log, user_email in rows:
        changed_fields = _collapse_diff_values(log.changed_fields)
        related_id = (changed_fields or {}).get("related_record_id")
        related_uuid = _related_uuid(related_id)
        if related_uuid is not None and related_uuid in labels:
            changed_fields = {**(changed_fields or {}), "related_record_label": labels[related_uuid]}
        items.append(
            AuditLogRead(
                id=log.id,
                record_type=log.record_type,
                record_id=log.record_id,
                record_label=_delete_snapshot_label(log) or labels.get(log.record_id, str(log.record_id)[:8]),
                user_id=log.user_id,
                user_name=user_email or (str(log.user_id)[:8] if log.user_id else None),
                action=log.action,
                changed_fields=changed_fields,
                created_at=log.created_at,
            )
        )
    return Page(total=total or 0, page=page, page_size=page_size, items=items)
