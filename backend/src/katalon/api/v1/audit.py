import uuid

from fastapi import APIRouter, Query
from sqlalchemy import select

from katalon.core.dependencies import DBDep
from katalon.core.models import AuditLog, Entity, Object, Occurrence, Place, Procedure, User
from katalon.core.schemas import AuditLogRead

router = APIRouter(prefix="/audit", tags=["audit"])


async def _resolve_record_labels(db, logs: list[AuditLog]) -> dict[uuid.UUID, str]:
    """Fetch display labels (idno or title/name from metadata) for audit log records."""
    by_type: dict[str, list[uuid.UUID]] = {}
    for log in logs:
        by_type.setdefault(log.record_type, []).append(log.record_id)

    labels: dict[uuid.UUID, str] = {}

    if "object" in by_type:
        result = await db.execute(select(Object.id, Object.idno, Object.metadata_).where(Object.id.in_(by_type["object"])))
        for id_, idno, md in result.all():
            labels[id_] = idno or (md.get("title") if md else None) or str(id_)[:8]

    if "entity" in by_type:
        result = await db.execute(select(Entity.id, Entity.metadata_).where(Entity.id.in_(by_type["entity"])))
        for id_, md in result.all():
            labels[id_] = (md.get("name") if md else None) or str(id_)[:8]

    if "place" in by_type:
        result = await db.execute(select(Place.id, Place.metadata_).where(Place.id.in_(by_type["place"])))
        for id_, md in result.all():
            labels[id_] = (md.get("name") if md else None) or str(id_)[:8]

    if "occurrence" in by_type:
        result = await db.execute(select(Occurrence.id, Occurrence.metadata_).where(Occurrence.id.in_(by_type["occurrence"])))
        for id_, md in result.all():
            labels[id_] = (md.get("title") if md else None) or str(id_)[:8]

    if "procedure" in by_type:
        result = await db.execute(select(Procedure.id, Procedure.idno, Procedure.reference_number).where(Procedure.id.in_(by_type["procedure"])))
        for id_, idno, reference_number in result.all():
            labels[id_] = idno or reference_number or str(id_)[:8]

    return labels


@router.get("", response_model=list[AuditLogRead])
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
    labels = await _resolve_record_labels(db, logs)

    out: list[AuditLogRead] = []
    for log, user_email in rows:
        out.append(AuditLogRead(
            id=log.id,
            record_type=log.record_type,
            record_id=log.record_id,
            record_label=labels.get(log.record_id, str(log.record_id)[:8]),
            user_id=log.user_id,
            user_name=user_email or (str(log.user_id)[:8] if log.user_id else None),
            action=log.action,
            changed_fields=log.changed_fields,
            created_at=log.created_at,
        ))
    return out
