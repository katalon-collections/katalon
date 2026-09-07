# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from katalon.core.dependencies import DBDep, require_admin_or_editor
from katalon.core.models import FieldDefinition, Procedure, Relation, User
from katalon.core.schemas import RelationCreate, RelationRead, RelationUpdate
from katalon.services.audit_service import diff_fields, log_change
from katalon.services.relation_service import (
    get_active_loan_out_for_object,
    lock_objects,
    procedure_object_pair,
    resolve_relation_labels,
    validate_relation_endpoint,
)
from katalon.services.relation_type_service import validate_relation_type_applicability

_LOGGABLE_RECORD_TYPES = {
    "object",
    "entity",
    "place",
    "occurrence",
    "procedure",
    "collection",
    "storage_location",
}


async def _log_relation_change(
    db: DBDep,
    rel: Relation,
    user_id: uuid.UUID,
    *,
    action: str,
    changed_fields: dict[str, Any],
) -> None:
    """Log a relation change against both endpoints it connects, when they're auditable record types."""
    for record_type, record_id, other_type, other_id in (
        (rel.from_type, rel.from_id, rel.to_type, rel.to_id),
        (rel.to_type, rel.to_id, rel.from_type, rel.from_id),
    ):
        if record_type not in _LOGGABLE_RECORD_TYPES:
            continue
        await log_change(
            db,
            record_type=record_type,
            record_id=record_id,
            user_id=user_id,
            action=action,
            changed_fields={
                **changed_fields,
                "relation_id": str(rel.id),
                "related_record_type": other_type,
                "related_record_id": str(other_id),
            },
        )


router = APIRouter(prefix="/relations", tags=["relations"])


@router.get(
    "", response_model=list[RelationRead], summary="List relations, optionally filtered by endpoint"
)
async def list_relations(
    db: DBDep,
    from_type: str | None = None,
    from_id: uuid.UUID | None = None,
    to_type: str | None = None,
    to_id: uuid.UUID | None = None,
    limit: int = Query(100, ge=1, le=500),
    include_subcollections: bool = False,
    include_sublocations: bool = False,
) -> list[RelationRead]:
    query = select(Relation).limit(limit).order_by(Relation.created_at.desc())
    if from_type:
        query = query.where(Relation.from_type == from_type)
    if from_id:
        if from_type == "collection" and include_subcollections:
            from katalon.services.collection_service import get_collection_subtree_ids

            sub_ids = await get_collection_subtree_ids(db, from_id, public_only=False)
            query = query.where(Relation.from_id.in_(sub_ids))
        elif from_type == "storage_location" and include_sublocations:
            from katalon.services.storage_location_service import get_storage_location_subtree_ids

            sub_ids = await get_storage_location_subtree_ids(db, from_id)
            query = query.where(Relation.from_id.in_(sub_ids))
        else:
            query = query.where(Relation.from_id == from_id)
    if to_type:
        query = query.where(Relation.to_type == to_type)
    if to_id:
        if to_type == "collection" and include_subcollections:
            from katalon.services.collection_service import get_collection_subtree_ids

            sub_ids = await get_collection_subtree_ids(db, to_id, public_only=False)
            query = query.where(Relation.to_id.in_(sub_ids))
        elif to_type == "storage_location" and include_sublocations:
            from katalon.services.storage_location_service import get_storage_location_subtree_ids

            sub_ids = await get_storage_location_subtree_ids(db, to_id)
            query = query.where(Relation.to_id.in_(sub_ids))
        else:
            query = query.where(Relation.to_id == to_id)
    relations = list((await db.execute(query)).scalars().all())
    labels = await resolve_relation_labels(db, relations)
    return [
        RelationRead.model_validate(rel).model_copy(
            update={
                "from_label": labels.get((rel.from_type, rel.from_id)),
                "to_label": labels.get((rel.to_type, rel.to_id)),
            }
        )
        for rel in relations
    ]


@router.post(
    "",
    response_model=RelationRead,
    status_code=201,
    summary="Create a relation between two records",
    responses={
        403: {"description": "Insufficient permissions"},
        409: {"description": "Object is already in an active loan-out procedure"},
        422: {"description": "Relation type not allowed for this type pair"},
    },
)
async def create_relation(
    data: RelationCreate,
    db: DBDep,
    current_user: User = require_admin_or_editor(),
) -> Relation:
    bound_field = await db.scalar(
        select(FieldDefinition.id).where(
            FieldDefinition.target_type == data.from_type,
            FieldDefinition.field_type == "relation",
            FieldDefinition.is_deleted.is_(False),
            FieldDefinition.settings["target_type"].astext == data.to_type,
            FieldDefinition.settings["fixed_relation_type"].astext == data.relation_type,
        )
    )
    if bound_field is not None:
        raise HTTPException(
            status_code=409,
            detail="Diese feldgebundene Beziehung wird im zugehörigen Formularfeld gepflegt.",
        )
    duplicate = await db.scalar(
        select(Relation.id).where(
            Relation.from_type == data.from_type,
            Relation.from_id == data.from_id,
            Relation.to_type == data.to_type,
            Relation.to_id == data.to_id,
            Relation.relation_type == data.relation_type,
        )
    )
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="Diese Beziehung existiert bereits.")
    from_error = await validate_relation_endpoint(db, data.from_type, data.from_id)
    if from_error:
        raise HTTPException(status_code=422, detail=from_error)
    to_error = await validate_relation_endpoint(db, data.to_type, data.to_id)
    if to_error:
        raise HTTPException(status_code=422, detail=to_error)
    pair = procedure_object_pair(data.from_type, data.from_id, data.to_type, data.to_id)
    if pair:
        procedure_id, object_id = pair
        procedure = (
            await db.execute(select(Procedure).where(Procedure.id == procedure_id))
        ).scalar_one_or_none()
        if procedure and procedure.procedure_type == "loan_out" and procedure.status == "active":
            await lock_objects(db, [object_id])
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
    applicability_error = await validate_relation_type_applicability(
        db, data.from_type, data.to_type, data.relation_type
    )
    if applicability_error:
        raise HTTPException(status_code=422, detail=applicability_error)
    rel = Relation(
        from_type=data.from_type,
        from_id=data.from_id,
        to_type=data.to_type,
        to_id=data.to_id,
        relation_type=data.relation_type,
        metadata_=data.metadata_,
    )
    db.add(rel)
    await db.flush()
    await _log_relation_change(
        db,
        rel,
        current_user.id,
        action="relation_add",
        changed_fields={"relation_type": rel.relation_type},
    )
    return rel


@router.put(
    "/{relation_id}",
    response_model=RelationRead,
    summary="Update a relation's type or metadata",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Relation not found"},
        422: {"description": "Relation type not allowed for this type pair"},
    },
)
async def update_relation(
    relation_id: uuid.UUID,
    data: RelationUpdate,
    db: DBDep,
    current_user: User = require_admin_or_editor(),
) -> Relation:
    result = await db.execute(select(Relation).where(Relation.id == relation_id))
    rel = result.scalar_one_or_none()
    if not rel:
        raise HTTPException(status_code=404, detail="Relation nicht gefunden")
    old_fields = {"relation_type": rel.relation_type, "metadata": rel.metadata_}
    if data.relation_type is not None:
        applicability_error = await validate_relation_type_applicability(
            db, rel.from_type, rel.to_type, data.relation_type
        )
        if applicability_error:
            raise HTTPException(status_code=422, detail=applicability_error)
        rel.relation_type = data.relation_type
    if data.metadata_ is not None:
        rel.metadata_ = data.metadata_
    await db.flush()
    diff = diff_fields(old_fields, {"relation_type": rel.relation_type, "metadata": rel.metadata_})
    if diff:
        await _log_relation_change(
            db, rel, current_user.id, action="relation_update", changed_fields=diff
        )
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
    current_user: User = require_admin_or_editor(),
) -> None:
    result = await db.execute(select(Relation).where(Relation.id == relation_id))
    rel = result.scalar_one_or_none()
    if not rel:
        raise HTTPException(status_code=404, detail="Relation nicht gefunden")
    await _log_relation_change(
        db,
        rel,
        current_user.id,
        action="relation_delete",
        changed_fields={"relation_type": rel.relation_type},
    )
    await db.delete(rel)
