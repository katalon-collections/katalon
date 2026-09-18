# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.config import settings
from katalon.core.models import (
    Collection,
    Entity,
    MediaFile,
    Object,
    Occurrence,
    Place,
    RecordSubtype,
    Relation,
)
from katalon.integrations.metadata_format import (
    ExportMediaItem,
    ExportRecordContext,
    ExportRecordSummary,
    ExportRelation,
)
from katalon.services.public_metadata_service import filter_public_metadata, load_public_fields
from katalon.services.search_service import _extract_title

_MODEL_MAP: dict[str, type[Any]] = {
    "object": Object,
    "entity": Entity,
    "place": Place,
    "occurrence": Occurrence,
    "collection": Collection,
}

# Internal types strictly excluded from public export contexts
_EXCLUDED_RELATION_TARGET_TYPES: set[str] = {"storage_location", "procedure"}


async def build_export_context_from_db(
    db: AsyncSession,
    record_type: str,
    record_id: uuid.UUID,
    base_url: str = "",
) -> ExportRecordContext:
    """Build a complete, security-filtered ExportRecordContext directly from PostgreSQL."""
    clean_base = (base_url or settings.katalon_base_url or "").rstrip("/")
    model = _MODEL_MAP.get(record_type)
    if not model:
        raise ValueError(f"Nicht unterstützter Datensatztyp: {record_type}")

    record = await db.get(model, record_id)
    if not record or getattr(record, "is_deleted", False):
        raise ValueError(f"Datensatz {record_type}/{record_id} nicht gefunden oder gelöscht.")

    # 1. Record summary
    raw_md = getattr(record, "metadata_", None) or {}
    subtype = getattr(record, f"{record_type}_type", None) or getattr(record, "subtype", None)
    title = getattr(record, "title", None) or _extract_title(raw_md) or getattr(record, "idno", None) or ""
    status = getattr(record, "status", "public") or "public"

    canonical_url = f"{clean_base}/{record_type}/{record_id}" if clean_base else None

    subtype_concept_source = None
    subtype_concept_id = None
    subtype_concept_uri = None
    subtype_concept_label = None
    if subtype:
        res_st = await db.execute(
            select(RecordSubtype).where(
                RecordSubtype.primary_type == record_type,
                RecordSubtype.name == str(subtype),
            )
        )
        st_obj = res_st.scalar_one_or_none()
        if st_obj:
            subtype_concept_source = st_obj.concept_source
            subtype_concept_id = st_obj.concept_id
            subtype_concept_uri = st_obj.concept_uri
            lbl = st_obj.label or {}
            subtype_concept_label = (
                st_obj.concept_label
                or lbl.get("de")
                or lbl.get("en")
                or next((str(v) for v in lbl.values() if v), None)
                or st_obj.name
            )

    summary = ExportRecordSummary(
        id=str(record.id),
        idno=getattr(record, "idno", None),
        record_type=record_type,
        target_subtype=str(subtype) if subtype else None,
        title=str(title) if title else None,
        status=str(status),
        created_at=record.created_at.isoformat() if getattr(record, "created_at", None) else None,
        updated_at=record.updated_at.isoformat() if getattr(record, "updated_at", None) else None,
        canonical_url=canonical_url,
        subtype_concept_source=subtype_concept_source,
        subtype_concept_id=subtype_concept_id,
        subtype_concept_uri=subtype_concept_uri,
        subtype_concept_label=subtype_concept_label,
    )

    # 2. Public fields only (internal fields excluded)
    public_fields = await load_public_fields(db, record_type)
    fields = filter_public_metadata(raw_md, public_fields, subtype)

    # 3. Public relations only (excluding storage_location & procedure; excluding deleted/non-public targets)
    async def _resolve_relation(
        other_type: str, other_id: uuid.UUID, relation_type: str, rel_metadata: dict[str, Any], rel_id: uuid.UUID, direction: str
    ) -> ExportRelation | None:
        if other_type in _EXCLUDED_RELATION_TARGET_TYPES:
            return None
        other_model = _MODEL_MAP.get(other_type)
        if not other_model:
            return None
        other_rec = await db.get(other_model, other_id)
        if not other_rec or getattr(other_rec, "is_deleted", False):
            return None
        other_status = getattr(other_rec, "status", "public")
        if other_status not in ("public", None):
            return None

        other_md = getattr(other_rec, "metadata_", None) or {}
        other_title = getattr(other_rec, "title", None) or _extract_title(other_md) or getattr(other_rec, "idno", None) or ""

        other_public_fields = await load_public_fields(db, other_type)
        other_subtype = getattr(other_rec, f"{other_type}_type", None) or getattr(other_rec, "subtype", None)
        filtered_other_values = filter_public_metadata(other_md, other_public_fields, other_subtype)

        return ExportRelation(
            id=str(rel_id),
            direction=direction,
            relation_type=relation_type,
            target_type=other_type,
            target_id=str(other_id),
            target_label=str(other_title) if other_title else None,
            target_idno=getattr(other_rec, "idno", None),
            metadata=dict(rel_metadata or {}),
            target_values=filtered_other_values,
        )

    relations: list[ExportRelation] = []
    outbound_res = await db.execute(
        select(Relation).where(
            Relation.from_type == record_type,
            Relation.from_id == record_id,
        )
    )
    for rel in outbound_res.scalars().all():
        resolved = await _resolve_relation(rel.to_type, rel.to_id, rel.relation_type, rel.metadata_, rel.id, "outbound")
        if resolved:
            relations.append(resolved)

    inbound_res = await db.execute(
        select(Relation).where(
            Relation.to_type == record_type,
            Relation.to_id == record_id,
        )
    )
    for rel in inbound_res.scalars().all():
        resolved = await _resolve_relation(rel.from_type, rel.from_id, rel.relation_type, rel.metadata_, rel.id, "inbound")
        if resolved:
            relations.append(resolved)

    # 4. Public media representations only (non-public media excluded)
    media: list[ExportMediaItem] = []
    if record_type == "object":
        media_res = await db.execute(
            select(MediaFile).where(
                MediaFile.object_id == record_id,
                MediaFile.is_public.is_(True),
                MediaFile.deleted_at.is_(None),
            ).order_by(MediaFile.is_primary.desc(), MediaFile.created_at)
        )
        for mf in media_res.scalars().all():
            media_url = f"{clean_base}/api/v1/media/{mf.id}/download" if clean_base else f"/api/v1/media/{mf.id}/download"
            iiif_url = f"{clean_base}/iiif/3/{mf.id}/full/max/0/default.jpg" if clean_base and mf.iiif_storage_key else None
            rights_holder_str = None
            if mf.rights_holder:
                rights_holder_str = (
                    mf.rights_holder.get("name")
                    or mf.rights_holder.get("label")
                    or str(mf.rights_holder)
                )

            media.append(
                ExportMediaItem(
                    id=str(mf.id),
                    filename=mf.filename,
                    mime_type=mf.mime_type,
                    role="primary" if mf.is_primary else "representation",
                    is_primary=mf.is_primary,
                    is_public=mf.is_public,
                    url=media_url,
                    iiif_url=iiif_url,
                    license_uri=mf.license_uri,
                    rights_holder=rights_holder_str,
                )
            )

    return ExportRecordContext(
        record=summary,
        fields=fields,
        relations=relations,
        media=media,
    )
