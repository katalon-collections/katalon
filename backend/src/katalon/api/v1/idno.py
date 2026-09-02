# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select

from katalon.core.dependencies import DBDep, require_admin_or_editor
from katalon.core.models import AdminConfig, User
from katalon.services.idno_service import peek_next_idno

router = APIRouter(prefix="/idno", tags=["idno"])

_VALID_TYPES = frozenset({"object", "entity", "place", "occurrence", "procedure"})


class NextIdnoResponse(BaseModel):
    next: str | None


@router.get(
    "/next",
    response_model=NextIdnoResponse,
    summary="Preview the next suggested idno for a record type without incrementing the counter",
    responses={
        401: {"description": "Missing, invalid, or expired credentials"},
        403: {"description": "Insufficient permissions"},
    },
)
async def get_next_idno(
    db: DBDep,
    type: str = Query(..., description="Primary record type"),
    _: User = require_admin_or_editor(),
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
