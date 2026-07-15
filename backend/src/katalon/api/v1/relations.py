import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from katalon.core.dependencies import DBDep, require_admin_or_editor
from katalon.core.models import Procedure, Relation
from katalon.core.schemas import RelationCreate, RelationRead, RelationUpdate
from katalon.services.relation_service import get_active_loan_out_for_object, procedure_object_pair

router = APIRouter(prefix="/relations", tags=["relations"])


@router.get("", response_model=list[RelationRead], summary="List relations, optionally filtered by endpoint")
async def list_relations(
    db: DBDep,
    from_type: str | None = None,
    from_id: uuid.UUID | None = None,
    to_type: str | None = None,
    to_id: uuid.UUID | None = None,
    limit: int = Query(100, ge=1, le=500),
) -> list[Relation]:
    query = select(Relation).limit(limit).order_by(Relation.created_at.desc())
    if from_type:
        query = query.where(Relation.from_type == from_type)
    if from_id:
        query = query.where(Relation.from_id == from_id)
    if to_type:
        query = query.where(Relation.to_type == to_type)
    if to_id:
        query = query.where(Relation.to_id == to_id)
    return list((await db.execute(query)).scalars().all())


@router.post(
    "",
    response_model=RelationRead,
    status_code=201,
    summary="Create a relation between two records",
    responses={
        403: {"description": "Insufficient permissions"},
        409: {"description": "Object is already in an active loan-out procedure"},
    },
)
async def create_relation(
    data: RelationCreate,
    db: DBDep,
    current_user=require_admin_or_editor(),
) -> Relation:
    pair = procedure_object_pair(data.from_type, data.from_id, data.to_type, data.to_id)
    if pair:
        procedure_id, object_id = pair
        procedure = (
            await db.execute(select(Procedure).where(Procedure.id == procedure_id))
        ).scalar_one_or_none()
        if procedure and procedure.procedure_type == "loan_out" and procedure.status == "active":
            existing = await get_active_loan_out_for_object(
                db,
                object_id,
                exclude_procedure_id=procedure_id,
            )
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail="Objekt ist bereits in einem aktiven Ausleihvorgang.",
                )
    rel = Relation(
        from_type=data.from_type, from_id=data.from_id,
        to_type=data.to_type, to_id=data.to_id,
        relation_type=data.relation_type, metadata_=data.metadata_,
    )
    db.add(rel)
    await db.flush()
    return rel


@router.put(
    "/{relation_id}",
    response_model=RelationRead,
    summary="Update a relation's type or metadata",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Relation not found"},
    },
)
async def update_relation(
    relation_id: uuid.UUID, data: RelationUpdate, db: DBDep, current_user=require_admin_or_editor()
) -> Relation:
    result = await db.execute(select(Relation).where(Relation.id == relation_id))
    rel = result.scalar_one_or_none()
    if not rel:
        raise HTTPException(status_code=404, detail="Relation nicht gefunden")
    if data.relation_type is not None:
        rel.relation_type = data.relation_type
    if data.metadata_ is not None:
        rel.metadata_ = data.metadata_
    await db.flush()
    return rel


@router.delete(
    "/{relation_id}",
    status_code=204,
    summary="Delete a relation",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Relation not found"},
    },
)
async def delete_relation(
    relation_id: uuid.UUID,
    db: DBDep,
    current_user=require_admin_or_editor(),
) -> None:
    result = await db.execute(select(Relation).where(Relation.id == relation_id))
    rel = result.scalar_one_or_none()
    if not rel:
        raise HTTPException(status_code=404, detail="Relation nicht gefunden")
    await db.delete(rel)
