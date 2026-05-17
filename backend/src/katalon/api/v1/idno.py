from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select

from katalon.core.dependencies import DBDep, require_role
from katalon.core.models import AdminConfig
from katalon.services.idno_service import peek_next_idno

router = APIRouter(prefix="/idno", tags=["idno"])

_VALID_TYPES = frozenset({"object", "entity", "place", "occurrence"})


class NextIdnoResponse(BaseModel):
    next: str | None


@router.get("/next", response_model=NextIdnoResponse)
async def get_next_idno(
    db: DBDep,
    type: str = Query(..., description="Primary record type: object / entity / place / occurrence"),
    _=require_role("editor"),
) -> NextIdnoResponse:
    """Return the next suggested idno for a given record type WITHOUT incrementing the counter."""
    if type not in _VALID_TYPES:
        return NextIdnoResponse(next=None)

    result = await db.execute(select(AdminConfig).where(AdminConfig.key == "default"))
    config = result.scalar_one_or_none()
    if config is None:
        return NextIdnoResponse(next=None)

    schema = (config.idno_schemas or {}).get(type)
    if not schema:
        return NextIdnoResponse(next=None)

    suggested = await peek_next_idno(db, type, schema)
    return NextIdnoResponse(next=suggested)
