# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from katalon.api.v1.form_variants import _validate_target_type
from katalon.api.v1.schema_admin import _ensure_schema_subtype_exists
from katalon.core.dependencies import CurrentUser, DBDep, require_role
from katalon.core.models import FieldDefinition, FormSection
from katalon.core.schemas import FormSectionCreate, FormSectionRead

router = APIRouter(prefix="/form-sections", tags=["form-sections"])


async def _validate_section(data: FormSectionCreate, db: DBDep) -> None:
    _validate_target_type(data.target_type)
    await _ensure_schema_subtype_exists(db, data.target_type, data.target_subtype)
    if not any(isinstance(label, str) and label.strip() for label in data.label.values()):
        raise HTTPException(status_code=422, detail="Ein Formularabschnitt benötigt einen Anzeigenamen.")
    result = await db.execute(
        select(FieldDefinition.name).where(
            FieldDefinition.target_type == data.target_type,
            FieldDefinition.is_deleted.is_(False),
            FieldDefinition.parent_id.is_(None),
            (FieldDefinition.target_subtype.is_(None))
            | (FieldDefinition.target_subtype == data.target_subtype),
        )
    )
    known = set(result.scalars().all())
    unknown = set(data.field_names) - known
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unbekannte Felder: {', '.join(sorted(unknown))}")
    if len(data.field_names) != len(set(data.field_names)):
        raise HTTPException(status_code=422, detail="Ein Feld darf nur einmal in einem Abschnitt vorkommen.")


@router.get("", response_model=list[FormSectionRead])
async def list_form_sections(
    db: DBDep,
    current_user: CurrentUser,
    target_type: str = Query(...),
    subtype: str | None = Query(default=None),
) -> list[FormSection]:
    _validate_target_type(target_type)
    result = await db.execute(
        select(FormSection)
        .where(
            FormSection.target_type == target_type,
            (FormSection.target_subtype.is_(None)) | (FormSection.target_subtype == subtype),
        )
        .order_by(FormSection.sort_order, FormSection.id)
    )
    return list(result.scalars().all())


@router.post("", response_model=FormSectionRead, status_code=201, dependencies=[require_role("admin")])
async def create_form_section(data: FormSectionCreate, db: DBDep) -> FormSection:
    await _validate_section(data, db)
    section = FormSection(**data.model_dump())
    db.add(section)
    await db.flush()
    return section


@router.put("/{section_id}", response_model=FormSectionRead, dependencies=[require_role("admin")])
async def update_form_section(section_id: uuid.UUID, data: FormSectionCreate, db: DBDep) -> FormSection:
    section = await db.get(FormSection, section_id)
    if section is None:
        raise HTTPException(status_code=404, detail="Formularabschnitt nicht gefunden.")
    await _validate_section(data, db)
    for field, value in data.model_dump().items():
        setattr(section, field, value)
    await db.flush()
    return section


@router.delete("/{section_id}", status_code=204, dependencies=[require_role("admin")])
async def delete_form_section(section_id: uuid.UUID, db: DBDep) -> None:
    section = await db.get(FormSection, section_id)
    if section is None:
        raise HTTPException(status_code=404, detail="Formularabschnitt nicht gefunden.")
    await db.delete(section)
    await db.flush()
