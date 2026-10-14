# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
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
from katalon.core.visibility import PUBLIC_STATUSES
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


# Inbound relations embedded in the export context stored in the search index.
# A collection with 30,000 member postcards otherwise produced a 46 MB document
# (every member with all its public field values). Above this count the index
# copy omits inbound relations and exporters rebuild the full context from the
# database for that one record (see expand_omitted_contexts).
INDEX_MAX_INBOUND_RELATIONS = 200


def _is_deleted(record: Any) -> bool:
    # Records soft-delete via deleted_at; they have no is_deleted column.
    return getattr(record, "deleted_at", None) is not None


async def build_export_context_from_db(
    db: AsyncSession,
    record_type: str,
    record_id: uuid.UUID,
    base_url: str = "",
    *,
    max_inbound: int | None = None,
) -> ExportRecordContext:
    """Build a complete, security-filtered ExportRecordContext directly from PostgreSQL.

    ``max_inbound``: if the record has more inbound relations, they are left
    out and counted in ``inbound_relations_omitted`` (index copy only).
    """
    clean_base = (base_url or settings.katalon_base_url or "").rstrip("/")
    model = _MODEL_MAP.get(record_type)
    if not model:
        raise ValueError(f"Nicht unterstützter Datensatztyp: {record_type}")

    record = await db.get(model, record_id)
    if not record or _is_deleted(record):
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
    outbound = (
        await db.execute(
            select(Relation).where(Relation.from_type == record_type, Relation.from_id == record_id)
        )
    ).scalars().all()
    inbound_filter = (Relation.to_type == record_type, Relation.to_id == record_id)
    inbound_count = (
        await db.execute(select(func.count()).select_from(Relation).where(*inbound_filter))
    ).scalar_one()
    omitted = 0
    if max_inbound is not None and inbound_count > max_inbound:
        inbound: Sequence[Relation] = []
        omitted = inbound_count
    else:
        inbound = (await db.execute(select(Relation).where(*inbound_filter))).scalars().all()

    pending = [
        (rel, rel.to_type, rel.to_id, "outbound") for rel in outbound
    ] + [(rel, rel.from_type, rel.from_id, "inbound") for rel in inbound]

    # Load every target once per type (was: one get + one field query per relation).
    ids_by_type: dict[str, set[uuid.UUID]] = {}
    for _rel, other_type, other_id, _direction in pending:
        if other_type in _MODEL_MAP and other_type not in _EXCLUDED_RELATION_TARGET_TYPES:
            ids_by_type.setdefault(other_type, set()).add(other_id)
    targets: dict[tuple[str, uuid.UUID], Any] = {}
    public_fields_by_type: dict[str, Any] = {}
    for other_type, ids in ids_by_type.items():
        other_model = _MODEL_MAP[other_type]
        id_list = list(ids)
        for start in range(0, len(id_list), 1000):
            rows = await db.execute(
                select(other_model).where(other_model.id.in_(id_list[start : start + 1000]))
            )
            for other_rec in rows.scalars():
                targets[(other_type, other_rec.id)] = other_rec
        public_fields_by_type[other_type] = await load_public_fields(db, other_type)

    relations: list[ExportRelation] = []
    for rel, other_type, other_id, direction in pending:
        other_rec = targets.get((other_type, other_id))
        if other_rec is None or _is_deleted(other_rec):
            continue
        other_status = getattr(other_rec, "status", None)
        if other_status is not None and other_status not in PUBLIC_STATUSES:
            continue
        other_md = getattr(other_rec, "metadata_", None) or {}
        other_title = (
            getattr(other_rec, "title", None)
            or _extract_title(other_md)
            or getattr(other_rec, "idno", None)
            or ""
        )
        other_subtype = getattr(other_rec, f"{other_type}_type", None) or getattr(
            other_rec, "subtype", None
        )
        relations.append(
            ExportRelation(
                id=str(rel.id),
                direction=direction,
                relation_type=rel.relation_type,
                target_type=other_type,
                target_id=str(other_id),
                target_label=str(other_title) if other_title else None,
                target_idno=getattr(other_rec, "idno", None),
                metadata=dict(rel.metadata_ or {}),
                target_values=filter_public_metadata(
                    other_md, public_fields_by_type[other_type], other_subtype
                ),
            )
        )

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
            media_url = f"{clean_base}/v1/media/{mf.id}/download" if clean_base else f"/v1/media/{mf.id}/download"
            iiif_url = f"{clean_base}/iiif/3/{mf.id}/full/max/0/default.jpg" if clean_base and mf.iiif_storage_key else None
            rights_holder_str = None
            rights_holder_uri = None
            if mf.rights_holder:
                if isinstance(mf.rights_holder, dict):
                    rights_holder_str = (
                        mf.rights_holder.get("name")
                        or mf.rights_holder.get("label")
                    )
                    rights_holder_uri = mf.rights_holder.get("uri")
                else:
                    rights_holder_str = str(mf.rights_holder)

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
                    rights_holder_uri=rights_holder_uri,
                )
            )

    return ExportRecordContext(
        record=summary,
        fields=fields,
        relations=relations,
        media=media,
        inbound_relations_omitted=omitted,
    )


async def expand_omitted_contexts(db: AsyncSession, hits: list[dict[str, Any]]) -> None:
    """Replace index copies that left out inbound relations with the full
    context from the database, in place. Only records above
    INDEX_MAX_INBOUND_RELATIONS are affected (e.g. large collections)."""
    for hit in hits:
        source = hit.get("_source") or {}
        ec = source.get("export_context")
        if not isinstance(ec, dict) or not ec.get("inbound_relations_omitted"):
            continue
        record = ec.get("record") or {}
        try:
            full = await build_export_context_from_db(
                db, str(record.get("record_type")), uuid.UUID(str(record.get("id")))
            )
        except ValueError:
            continue
        source["export_context"] = full.to_dict()
