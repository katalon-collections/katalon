import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import AuditLog


async def log_change(
    db: AsyncSession,
    *,
    record_type: str,
    record_id: uuid.UUID,
    user_id: uuid.UUID | None,
    action: str,
    changed_fields: dict | None = None,
) -> None:
    entry = AuditLog(
        record_type=record_type,
        record_id=record_id,
        user_id=user_id,
        action=action,
        changed_fields=changed_fields or {},
    )
    db.add(entry)
    # session commit happens in get_db()
