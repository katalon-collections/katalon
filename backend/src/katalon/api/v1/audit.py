import uuid

from fastapi import APIRouter, Query
from sqlalchemy import select

from katalon.core.dependencies import DBDep
from katalon.core.models import AuditLog, User
from katalon.core.schemas import AuditLogRead

router = APIRouter(prefix="/audit", tags=["audit"])


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
    out: list[AuditLogRead] = []
    for log, user_email in rows:
        out.append(AuditLogRead(
            id=log.id,
            record_type=log.record_type,
            record_id=log.record_id,
            user_id=log.user_id,
            user_name=user_email or (str(log.user_id)[:8] if log.user_id else None),
            action=log.action,
            changed_fields=log.changed_fields,
            created_at=log.created_at,
        ))
    return out
