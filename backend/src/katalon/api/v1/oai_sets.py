from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from katalon.core.dependencies import CurrentUser, DBDep
from katalon.core.models import OAISet
from katalon.core.schemas import OAISetCreate, OAISetRead

router = APIRouter(prefix="/oai-sets", tags=["oai-pmh"])


@router.get(
    "",
    response_model=list[OAISetRead],
    summary="List OAI-PMH sets",
)
async def list_oai_sets(db: DBDep) -> list[OAISet]:
    result = await db.execute(select(OAISet).order_by(OAISet.set_spec))
    return list(result.scalars().all())


@router.post(
    "",
    response_model=OAISetRead,
    status_code=201,
    summary="Create an OAI-PMH set",
    responses={
        403: {"description": "Insufficient permissions"},
        400: {"description": "set_spec already taken"},
    },
)
async def create_oai_set(data: OAISetCreate, db: DBDep, current_user: CurrentUser) -> OAISet:
    if current_user.role not in {"admin", "superuser"}:
        raise HTTPException(status_code=403, detail="Nur Admins können OAI-Sets anlegen.")
    existing = await db.execute(select(OAISet).where(OAISet.set_spec == data.set_spec))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"set_spec '{data.set_spec}' bereits vergeben.")
    oai_set = OAISet(**data.model_dump())
    db.add(oai_set)
    await db.commit()
    await db.refresh(oai_set)
    return oai_set


@router.put(
    "/{set_id}",
    response_model=OAISetRead,
    summary="Update an OAI-PMH set",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "OAI set not found"},
        400: {"description": "set_spec already taken"},
    },
)
async def update_oai_set(
    set_id: uuid.UUID,
    data: OAISetCreate,
    db: DBDep,
    current_user: CurrentUser,
) -> OAISet:
    if current_user.role not in {"admin", "superuser"}:
        raise HTTPException(status_code=403, detail="Nur Admins können OAI-Sets bearbeiten.")
    result = await db.execute(select(OAISet).where(OAISet.id == set_id))
    oai_set = result.scalar_one_or_none()
    if not oai_set:
        raise HTTPException(status_code=404, detail="OAI-Set nicht gefunden.")
    conflict = await db.execute(
        select(OAISet).where(OAISet.set_spec == data.set_spec, OAISet.id != set_id)
    )
    if conflict.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"set_spec '{data.set_spec}' bereits vergeben.")
    for field, value in data.model_dump().items():
        setattr(oai_set, field, value)
    await db.commit()
    await db.refresh(oai_set)
    return oai_set


@router.delete(
    "/{set_id}",
    status_code=204,
    summary="Delete an OAI-PMH set",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "OAI set not found"},
    },
)
async def delete_oai_set(set_id: uuid.UUID, db: DBDep, current_user: CurrentUser) -> None:
    if current_user.role not in {"admin", "superuser"}:
        raise HTTPException(status_code=403, detail="Nur Admins können OAI-Sets löschen.")
    result = await db.execute(select(OAISet).where(OAISet.id == set_id))
    oai_set = result.scalar_one_or_none()
    if not oai_set:
        raise HTTPException(status_code=404, detail="OAI-Set nicht gefunden.")
    await db.delete(oai_set)
    await db.commit()
