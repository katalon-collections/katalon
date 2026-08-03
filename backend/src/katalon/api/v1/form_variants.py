from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from katalon.api.v1.schema_admin import (
    PROCEDURE_TYPES,
    SCHEMA_TARGET_TYPES,
    _ensure_schema_subtype_exists,
)
from katalon.core.dependencies import CurrentUser, DBDep, require_role
from katalon.core.models import FieldDefinition, FormVariant, FormVariantRoleDefault
from katalon.core.schemas import FormVariantCreate, FormVariantRead

router = APIRouter(prefix="/form-variants", tags=["form-variants"])


def _validate_target_type(target_type: str) -> None:
    if target_type not in SCHEMA_TARGET_TYPES or target_type == "vocabulary_term":
        raise HTTPException(status_code=422, detail="Ungültiger Zieltyp für Formularvarianten.")


async def _validate_field_names(
    db: DBDep, target_type: str, target_subtype: str | None, field_names: list[str]
) -> None:
    if not field_names:
        return
    result = await db.execute(
        select(FieldDefinition.name).where(
            FieldDefinition.target_type == target_type,
            FieldDefinition.is_deleted.is_(False),
            FieldDefinition.parent_id.is_(None),
            (FieldDefinition.target_subtype.is_(None))
            | (FieldDefinition.target_subtype == target_subtype),
        )
    )
    known = set(result.scalars().all())
    unknown = [name for name in field_names if name not in known]
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"Unbekannte Felder für diesen Typ/Subtyp: {', '.join(unknown)}",
        )


async def _unset_role_defaults(
    db: DBDep, target_type: str, target_subtype: str | None, roles: set[str], *, keep_variant_id: uuid.UUID
) -> None:
    result = await db.execute(
        select(FormVariantRoleDefault).where(
            FormVariantRoleDefault.target_type == target_type,
            FormVariantRoleDefault.target_subtype == target_subtype,
            FormVariantRoleDefault.role.in_(roles),
            FormVariantRoleDefault.variant_id != keep_variant_id,
        )
    )
    for row in result.scalars().all():
        await db.delete(row)


async def _read_with_role_defaults(db: DBDep, variant: FormVariant, current_role: str) -> FormVariantRead:
    result = await db.execute(
        select(FormVariantRoleDefault.role).where(
            FormVariantRoleDefault.variant_id == variant.id,
            FormVariantRoleDefault.role == current_role,
        )
    )
    default_for_roles = list(result.scalars().all())
    read = FormVariantRead.model_validate(variant)
    return read.model_copy(update={"default_for_roles": default_for_roles})


@router.get(
    "",
    response_model=list[FormVariantRead],
    summary="List form variants for a target type/subtype",
    responses={422: {"description": "Invalid target type"}},
)
async def list_form_variants(
    db: DBDep,
    current_user: CurrentUser,
    target_type: str = Query(...),
    subtype: str | None = Query(default=None),
) -> list[FormVariantRead]:
    _validate_target_type(target_type)
    q = select(FormVariant).where(
        FormVariant.target_type == target_type,
        FormVariant.is_deleted.is_(False),
        (FormVariant.target_subtype.is_(None)) | (FormVariant.target_subtype == subtype),
    )
    result = await db.execute(q.order_by(FormVariant.sort_order, FormVariant.name))
    variants = list(result.scalars().all())
    return [await _read_with_role_defaults(db, v, current_user.role) for v in variants]


@router.post(
    "",
    response_model=FormVariantRead,
    status_code=201,
    dependencies=[require_role("admin")],
    summary="Create a form variant",
    responses={403: {"description": "Insufficient permissions"}, 422: {"description": "Invalid target type, subtype, or field names"}},
)
async def create_form_variant(data: FormVariantCreate, db: DBDep) -> FormVariant:
    _validate_target_type(data.target_type)
    if data.target_type == "procedure":
        if data.target_subtype is not None and data.target_subtype not in PROCEDURE_TYPES:
            raise HTTPException(status_code=422, detail=f"Ungültiger Vorgangstyp '{data.target_subtype}'.")
    else:
        await _ensure_schema_subtype_exists(db, data.target_type, data.target_subtype)
    await _validate_field_names(db, data.target_type, data.target_subtype, data.field_names)

    variant = FormVariant(**data.model_dump())
    db.add(variant)
    await db.flush()
    return variant


@router.put(
    "/{variant_id}",
    response_model=FormVariantRead,
    dependencies=[require_role("admin")],
    summary="Update a form variant",
    responses={
        403: {"description": "Insufficient permissions"},
        404: {"description": "Form variant not found"},
        422: {"description": "Invalid target type, subtype, or field names"},
    },
)
async def update_form_variant(variant_id: uuid.UUID, data: FormVariantCreate, db: DBDep) -> FormVariant:
    variant = await db.get(FormVariant, variant_id)
    if variant is None or variant.is_deleted:
        raise HTTPException(status_code=404, detail="Formularvariante nicht gefunden.")

    _validate_target_type(data.target_type)
    if data.target_type == "procedure":
        if data.target_subtype is not None and data.target_subtype not in PROCEDURE_TYPES:
            raise HTTPException(status_code=422, detail=f"Ungültiger Vorgangstyp '{data.target_subtype}'.")
    else:
        await _ensure_schema_subtype_exists(db, data.target_type, data.target_subtype)
    await _validate_field_names(db, data.target_type, data.target_subtype, data.field_names)

    for field, value in data.model_dump().items():
        setattr(variant, field, value)
    await db.flush()
    return variant


@router.delete(
    "/{variant_id}",
    status_code=204,
    dependencies=[require_role("admin")],
    summary="Delete a form variant",
    responses={403: {"description": "Insufficient permissions"}, 404: {"description": "Form variant not found"}},
)
async def delete_form_variant(variant_id: uuid.UUID, db: DBDep) -> None:
    variant = await db.get(FormVariant, variant_id)
    if variant is None or variant.is_deleted:
        raise HTTPException(status_code=404, detail="Formularvariante nicht gefunden.")
    variant.is_deleted = True
    await db.flush()


@router.post(
    "/{variant_id}/role-defaults/{role}",
    status_code=204,
    dependencies=[require_role("admin")],
    summary="Set this variant as the default for a role in its target type/subtype scope",
    responses={403: {"description": "Insufficient permissions"}, 404: {"description": "Form variant not found"}},
)
async def set_role_default(variant_id: uuid.UUID, role: str, db: DBDep) -> None:
    variant = await db.get(FormVariant, variant_id)
    if variant is None or variant.is_deleted:
        raise HTTPException(status_code=404, detail="Formularvariante nicht gefunden.")

    await _unset_role_defaults(
        db, variant.target_type, variant.target_subtype, {role}, keep_variant_id=variant_id
    )
    existing = await db.execute(
        select(FormVariantRoleDefault).where(
            FormVariantRoleDefault.target_type == variant.target_type,
            FormVariantRoleDefault.target_subtype == variant.target_subtype,
            FormVariantRoleDefault.role == role,
            FormVariantRoleDefault.variant_id == variant_id,
        )
    )
    if existing.scalar_one_or_none() is None:
        db.add(
            FormVariantRoleDefault(
                target_type=variant.target_type,
                target_subtype=variant.target_subtype,
                role=role,
                variant_id=variant_id,
            )
        )
    await db.flush()


@router.delete(
    "/{variant_id}/role-defaults/{role}",
    status_code=204,
    dependencies=[require_role("admin")],
    summary="Remove this variant's default status for a role",
    responses={403: {"description": "Insufficient permissions"}, 404: {"description": "Role default not found"}},
)
async def remove_role_default(variant_id: uuid.UUID, role: str, db: DBDep) -> None:
    result = await db.execute(
        select(FormVariantRoleDefault).where(
            FormVariantRoleDefault.variant_id == variant_id,
            FormVariantRoleDefault.role == role,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Rollen-Default nicht gefunden.")
    await db.delete(row)
