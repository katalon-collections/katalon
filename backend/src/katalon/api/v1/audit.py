import uuid

from fastapi import APIRouter, Query
from sqlalchemy import select

from katalon.core.dependencies import DBDep
from katalon.core.models import AuditLog, Entity, Object, Occurrence, Place, Procedure, User
from katalon.core.schemas import AuditLogRead

router = APIRouter(prefix="/audit", tags=["audit"])

# Mirrors TITLE_FIELD_NAMES in frontend/admin/src/components/screens/ScreenForm.tsx —
# keep both lists in sync.
_TITLE_FIELD_NAMES = ["label", "title", "titel", "name", "display_name", "place_name", "bezeichnung"]


def _extract_title(md: dict | None) -> str | None:
    if not md:
        return None
    for key in _TITLE_FIELD_NAMES:
        val = md.get(key)
        if not val:
            continue
        if isinstance(val, str):
            return val
        if isinstance(val, list) and val:
            first = val[0]
            if isinstance(first, str):
                return first
            if isinstance(first, dict):
                return first.get("value") or first.get("label") or None
    return None


def _format_label(title: str | None, idno: str | None, fallback: str) -> str:
    if not title:
        return idno or fallback
    return f"{title} ({idno})" if idno else title


async def _resolve_record_labels(db, refs: list[tuple[str, uuid.UUID]]) -> dict[uuid.UUID, str]:
    """Fetch display labels ("title (idno)") for (record_type, record_id) pairs."""
    by_type: dict[str, list[uuid.UUID]] = {}
    for record_type, record_id in refs:
        by_type.setdefault(record_type, []).append(record_id)

    labels: dict[uuid.UUID, str] = {}

    for record_type, model in (("object", Object), ("entity", Entity), ("place", Place), ("occurrence", Occurrence)):
        if record_type not in by_type:
            continue
        result = await db.execute(select(model.id, model.idno, model.metadata_).where(model.id.in_(by_type[record_type])))
        for id_, idno, md in result.all():
            labels[id_] = _format_label(_extract_title(md), idno, str(id_)[:8])

    if "procedure" in by_type:
        result = await db.execute(select(Procedure.id, Procedure.idno, Procedure.reference_number).where(Procedure.id.in_(by_type["procedure"])))
        for id_, idno, reference_number in result.all():
            labels[id_] = idno or reference_number or str(id_)[:8]

    return labels


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
    if record_type:
        query = query.where(AuditLog.record_type == record_type)
    if record_id:
        query = query.where(AuditLog.record_id == record_id)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    if action:
        query = query.where(AuditLog.action == action)

    result = await db.execute(query)
    rows = result.all()
    logs = [log for log, _ in rows]

    refs = {(log.record_type, log.record_id) for log in logs}
    for log in logs:
        related_type = (log.changed_fields or {}).get("related_record_type")
        related_id = (log.changed_fields or {}).get("related_record_id")
        if related_type and related_id:
            refs.add((related_type, uuid.UUID(related_id)))
    labels = await _resolve_record_labels(db, list(refs))

    out: list[AuditLogRead] = []
    for log, user_email in rows:
        changed_fields = log.changed_fields
        related_id = (changed_fields or {}).get("related_record_id")
        if related_id and uuid.UUID(related_id) in labels:
            changed_fields = {**changed_fields, "related_record_label": labels[uuid.UUID(related_id)]}
        out.append(AuditLogRead(
            id=log.id,
            record_type=log.record_type,
            record_id=log.record_id,
            record_label=labels.get(log.record_id, str(log.record_id)[:8]),
            user_id=log.user_id,
            user_name=user_email or (str(log.user_id)[:8] if log.user_id else None),
            action=log.action,
            changed_fields=changed_fields,
            created_at=log.created_at,
        ))
    return out
