import uuid

from fastapi import APIRouter, Query
from sqlalchemy import select

from katalon.core.dependencies import DBDep
from katalon.core.models import AuditLog
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
) -> list[AuditLog]:
    query = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    if record_type:
        query = query.where(AuditLog.record_type == record_type)
    if record_id:
        query = query.where(AuditLog.record_id == record_id)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    if action:
        query = query.where(AuditLog.action == action)

    result = await db.execute(query)
    return list(result.scalars().all())
