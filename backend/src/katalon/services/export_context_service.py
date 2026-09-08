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
    )

    # 2. Public fields only (internal fields excluded)
    public_fields = await load_public_fields(db, record_type)
    fields = filter_public_metadata(raw_md, public_fields, subtype)

    # 3. Public relations only (excluding storage_location & procedure; excluding deleted/non-public targets)
    relations: list[ExportRelation] = []
    rel_res = await db.execute(
        select(Relation).where(
            Relation.from_type == record_type,
            Relation.from_id == record_id,
        )
    )
    for rel in rel_res.scalars().all():
        if rel.to_type in _EXCLUDED_RELATION_TARGET_TYPES:
            continue
        target_model = _MODEL_MAP.get(rel.to_type)
        if not target_model:
            continue
        target_rec = await db.get(target_model, rel.to_id)
        if not target_rec or getattr(target_rec, "is_deleted", False):
            continue
        # Check target visibility
        target_status = getattr(target_rec, "status", "public")
        if target_status not in ("public", None):
            continue

        target_md = getattr(target_rec, "metadata_", None) or {}
        target_title = getattr(target_rec, "title", None) or _extract_title(target_md) or getattr(target_rec, "idno", None) or ""

        # Filter target public values
        target_public_fields = await load_public_fields(db, rel.to_type)
        target_subtype = getattr(target_rec, f"{rel.to_type}_type", None) or getattr(target_rec, "subtype", None)
        filtered_target_values = filter_public_metadata(target_md, target_public_fields, target_subtype)

        relations.append(
            ExportRelation(
                id=str(rel.id),
                direction="outbound",
                relation_type=rel.relation_type,
                target_type=rel.to_type,
                target_id=str(rel.to_id),
                target_label=str(target_title) if target_title else None,
                target_idno=getattr(target_rec, "idno", None),
                metadata=dict(rel.metadata_ or {}),
                target_values=filtered_target_values,
            )
        )

    # 4. Public media representations only (non-public media excluded)
    media: list[ExportMediaItem] = []
    if record_type == "object":
        media_res = await db.execute(
            select(MediaFile).where(
                MediaFile.object_id == record_id,
                MediaFile.is_public.is_(True),
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
