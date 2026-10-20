# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import copy
import logging
import uuid
from collections.abc import Iterable, Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.config import settings
from katalon.core.media_storage import iiif_identifier
from katalon.core.models import (
    Collection,
    Entity,
    ExportMappingRule,
    ExportMappingSet,
    FieldDefinition,
    MediaFile,
    Object,
    Occurrence,
    Place,
    RecordSubtype,
    Relation,
    VocabularyTerm,
)
from katalon.core.visibility import PUBLIC_STATUSES
from katalon.integrations.licenses import license_label
from katalon.integrations.markdown_text import markdown_to_plain_text
from katalon.integrations.metadata_format import (
    EXPORT_CONTEXT_VERSION,
    ExportMediaItem,
    ExportRecordContext,
    ExportRecordSummary,
    ExportRelation,
)
from katalon.services.public_metadata_service import filter_public_metadata, load_public_fields
from katalon.services.search_service import _extract_title

logger = logging.getLogger(__name__)

_MODEL_MAP: dict[str, type[Any]] = {
    "object": Object,
    "entity": Entity,
    "place": Place,
    "occurrence": Occurrence,
    "collection": Collection,
}

# Record types that get an export context (index copy, OAI, exports).
EXPORT_CONTEXT_TYPES: frozenset[str] = frozenset(_MODEL_MAP)

# Internal types strictly excluded from public export contexts
_EXCLUDED_RELATION_TARGET_TYPES: set[str] = {"storage_location", "procedure"}


# Inbound relations embedded in the export context stored in the search index.
# A collection with 30,000 member postcards otherwise produced a 46 MB document
# (every member with all its public field values). Above this count the index
# copy omits inbound relations and exporters rebuild the full context from the
# database for that one record (see refresh_index_contexts).
INDEX_MAX_INBOUND_RELATIONS = 200


def _is_deleted(record: Any) -> bool:
    # Records soft-delete via deleted_at; they have no is_deleted column.
    return getattr(record, "deleted_at", None) is not None


def _record_subtype(record: Any, record_type: str) -> Any:
    return getattr(record, f"{record_type}_type", None) or getattr(record, "subtype", None)


def _record_title(record: Any) -> str:
    md = getattr(record, "metadata_", None) or {}
    return str(
        getattr(record, "title", None) or _extract_title(md) or getattr(record, "idno", None) or ""
    )


def _normalize_mime(mime_type: str | None) -> str:
    value = (mime_type or "").strip().lower()
    return {"image/jpg": "image/jpeg", "image/pjpeg": "image/jpeg", "image/tif": "image/tiff"}.get(
        value, value
    )


async def collect_via_relation_types(
    db: AsyncSession, *, extra_rules: Iterable[Any] = ()
) -> set[str]:
    """Relation types that published mappings follow one step further (source_config.via).

    Only these second-level relations are loaded into export contexts, so the
    index does not grow by every relation of every related record.
    """
    rows = await db.execute(
        select(ExportMappingRule.source_config)
        .join(ExportMappingSet, ExportMappingRule.mapping_set_id == ExportMappingSet.id)
        .where(ExportMappingSet.status == "published", ExportMappingRule.is_enabled.is_(True))
    )
    configs = [cfg for (cfg,) in rows.all()]
    configs.extend(getattr(rule, "source_config", None) for rule in extra_rules)
    types: set[str] = set()
    for cfg in configs:
        via = (cfg or {}).get("via") if isinstance(cfg, dict) else None
        if isinstance(via, dict) and via.get("relation_type"):
            types.add(str(via["relation_type"]))
    return types


def _richtext_as_plain_text(
    fields: dict[str, Any], field_defs: Sequence[FieldDefinition]
) -> dict[str, Any]:
    """Return ``fields`` with richtext values (Markdown) as plain text for export formats."""
    by_id = {fd.id: fd for fd in field_defs}
    top: set[str] = set()
    grouped: dict[str, set[str]] = {}
    for fd in field_defs:
        if fd.field_type != "richtext":
            continue
        parent = by_id.get(fd.parent_id) if fd.parent_id is not None else None
        if parent is None:
            top.add(fd.name)
        else:
            grouped.setdefault(parent.name, set()).add(fd.name)
    if not top and not grouped:
        return fields

    def plain(value: Any) -> Any:
        if isinstance(value, str):
            return markdown_to_plain_text(value)
        if isinstance(value, list):
            return [plain(item) for item in value]
        if isinstance(value, dict):  # translatable {"de": ..., "en": ...}
            return {key: plain(item) for key, item in value.items()}
        return value

    result = dict(fields)
    for name in top & result.keys():
        result[name] = plain(result[name])
    for group, children in grouped.items():
        entries = result.get(group)
        if isinstance(entries, dict):
            entries = [entries]
        if not isinstance(entries, list):
            continue
        result[group] = [
            {key: plain(val) if key in children else val for key, val in entry.items()}
            if isinstance(entry, dict) else entry
            for entry in entries
        ]
    return result


async def _enrich_vocab_values(
    db: AsyncSession, fields: dict[str, Any], field_defs: Sequence[FieldDefinition]
) -> dict[str, Any]:
    """Return a copy of ``fields`` where vocab values carry the term's uri/exact_match_uris.

    One query for all referenced terms instead of one per value.
    """
    by_id = {fd.id: fd for fd in field_defs}
    top_vocab: set[str] = set()
    group_vocab: dict[str, set[str]] = {}
    for fd in field_defs:
        if fd.field_type != "vocab":
            continue
        parent = by_id.get(fd.parent_id) if fd.parent_id is not None else None
        if parent is None:
            top_vocab.add(fd.name)
        else:
            group_vocab.setdefault(parent.name, set()).add(fd.name)
    if not top_vocab and not group_vocab:
        return fields

    enriched = copy.deepcopy(fields)
    refs: list[dict[str, Any]] = []

    def collect(value: Any) -> None:
        for item in value if isinstance(value, list) else [value]:
            if isinstance(item, dict) and item.get("id"):
                refs.append(item)

    for name in top_vocab:
        collect(enriched.get(name))
    for group, children in group_vocab.items():
        for entry in enriched.get(group) or []:
            if isinstance(entry, dict):
                for child in children:
                    collect(entry.get(child))

    term_ids: set[uuid.UUID] = set()
    for ref in refs:
        try:
            term_ids.add(uuid.UUID(str(ref["id"])))
        except (ValueError, TypeError):
            continue
    if not term_ids:
        return enriched
    rows = await db.execute(
        select(VocabularyTerm.id, VocabularyTerm.uri, VocabularyTerm.exact_match_uris).where(
            VocabularyTerm.id.in_(term_ids)
        )
    )
    terms = {str(tid): (uri, list(exact or [])) for tid, uri, exact in rows.all()}
    for ref in refs:
        found = terms.get(str(ref["id"]).lower()) or terms.get(str(ref["id"]))
        if found is None:
            continue
        uri, exact = found
        if uri:
            ref["uri"] = uri
        if exact:
            ref["exact_match_uris"] = exact
    return enriched


async def _load_public_targets(
    db: AsyncSession, ids_by_type: dict[str, set[uuid.UUID]]
) -> tuple[dict[tuple[str, uuid.UUID], Any], dict[str, list[FieldDefinition]]]:
    targets: dict[tuple[str, uuid.UUID], Any] = {}
    public_fields_by_type: dict[str, list[FieldDefinition]] = {}
    for other_type, ids in ids_by_type.items():
        other_model = _MODEL_MAP[other_type]
        id_list = list(ids)
        for start in range(0, len(id_list), 1000):
            rows = await db.execute(
                select(other_model).where(other_model.id.in_(id_list[start : start + 1000]))
            )
            for other_rec in rows.scalars():
                if _is_deleted(other_rec):
                    continue
                other_status = getattr(other_rec, "status", None)
                if other_status is not None and other_status not in PUBLIC_STATUSES:
                    continue
                targets[(other_type, other_rec.id)] = other_rec
        public_fields_by_type[other_type] = await load_public_fields(db, other_type)
    return targets, public_fields_by_type


def _export_relation(
    rel: Relation,
    direction: str,
    other_type: str,
    other_id: uuid.UUID,
    other_rec: Any,
    public_fields: Sequence[FieldDefinition],
) -> ExportRelation:
    other_subtype = _record_subtype(other_rec, other_type)
    title = _record_title(other_rec)
    return ExportRelation(
        id=str(rel.id),
        direction=direction,
        relation_type=rel.relation_type,
        target_type=other_type,
        target_id=str(other_id),
        target_label=title or None,
        target_idno=getattr(other_rec, "idno", None),
        target_subtype=str(other_subtype) if other_subtype else None,
        metadata=dict(rel.metadata_ or {}),
        target_values=filter_public_metadata(
            getattr(other_rec, "metadata_", None) or {}, public_fields, other_subtype
        ),
    )


async def _attach_second_level(
    db: AsyncSession, relations: list[ExportRelation], via_types: set[str]
) -> None:
    """Fill target_relations of each first-level relation with the requested via types."""
    if not via_types or not relations:
        return
    keys = {
        (rel.target_type, uuid.UUID(rel.target_id))
        for rel in relations
        if rel.target_type in _MODEL_MAP
    }
    if not keys:
        return
    ids = [key[1] for key in keys]
    rows = (
        await db.execute(
            select(Relation).where(
                Relation.relation_type.in_(via_types),
                (Relation.from_id.in_(ids)) | (Relation.to_id.in_(ids)),
            )
        )
    ).scalars().all()
    pending: list[tuple[tuple[str, uuid.UUID], Relation, str, str, uuid.UUID]] = []
    for row in rows:
        if (row.from_type, row.from_id) in keys:
            pending.append(((row.from_type, row.from_id), row, "outbound", row.to_type, row.to_id))
        if (row.to_type, row.to_id) in keys:
            pending.append(((row.to_type, row.to_id), row, "inbound", row.from_type, row.from_id))
    ids_by_type: dict[str, set[uuid.UUID]] = {}
    for _owner, _row, _direction, other_type, other_id in pending:
        if other_type in _MODEL_MAP and other_type not in _EXCLUDED_RELATION_TARGET_TYPES:
            ids_by_type.setdefault(other_type, set()).add(other_id)
    targets, public_fields_by_type = await _load_public_targets(db, ids_by_type)
    by_owner: dict[tuple[str, uuid.UUID], list[ExportRelation]] = {}
    for owner, row, direction, other_type, other_id in pending:
        other_rec = targets.get((other_type, other_id))
        if other_rec is None:
            continue
        by_owner.setdefault(owner, []).append(
            _export_relation(
                row, direction, other_type, other_id, other_rec, public_fields_by_type[other_type]
            )
        )
    for rel in relations:
        if rel.target_type in _MODEL_MAP:
            rel.target_relations = by_owner.get((rel.target_type, uuid.UUID(rel.target_id)), [])


async def build_export_context_from_db(
    db: AsyncSession,
    record_type: str,
    record_id: uuid.UUID,
    base_url: str = "",
    *,
    max_inbound: int | None = None,
    via_relation_types: set[str] | None = None,
) -> ExportRecordContext:
    """Build a complete, security-filtered ExportRecordContext directly from PostgreSQL.

    ``max_inbound``: if the record has more inbound relations, they are left
    out and counted in ``inbound_relations_omitted`` (index copy only).
    ``via_relation_types``: second-level relation types to load; None = those
    requested by published mapping sets.
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
    subtype_concept_alternatives: list[dict[str, Any]] = []
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
            subtype_concept_alternatives = [
                dict(alt) for alt in (st_obj.concept_alternatives or []) if isinstance(alt, dict)
            ]

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
        subtype_concept_alternatives=subtype_concept_alternatives,
    )

    # 2. Public fields only (internal fields excluded); vocab values carry term URIs
    public_fields = await load_public_fields(db, record_type)
    fields = filter_public_metadata(raw_md, public_fields, subtype)
    fields = await _enrich_vocab_values(db, fields, public_fields)
    fields = _richtext_as_plain_text(fields, public_fields)

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
    targets, public_fields_by_type = await _load_public_targets(db, ids_by_type)

    relations: list[ExportRelation] = []
    for rel, other_type, other_id, direction in pending:
        other_rec = targets.get((other_type, other_id))
        if other_rec is None:
            continue
        relations.append(
            _export_relation(
                rel, direction, other_type, other_id, other_rec, public_fields_by_type[other_type]
            )
        )
    if via_relation_types is None:
        via_relation_types = await collect_via_relation_types(db)
    await _attach_second_level(db, relations, via_relation_types)

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
        iiif_host = (settings.cantaloupe_public_url or clean_base).rstrip("/")
        portal_api = f"{clean_base}/portal/v1" if clean_base else "/portal/v1"
        for mf in media_res.scalars().all():
            media_url = f"{clean_base}/v1/media/{mf.id}/download" if clean_base else f"/v1/media/{mf.id}/download"
            mime_type = _normalize_mime(mf.mime_type)
            iiif_base = (
                f"{iiif_host}/iiif/3/{iiif_identifier(mf.iiif_storage_key, mf.storage_key)}"
                if iiif_host and mf.iiif_storage_key and mf.status == "ready"
                else None
            )
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
                    mime_type=mime_type,
                    role="primary" if mf.is_primary else "representation",
                    is_primary=mf.is_primary,
                    is_public=mf.is_public,
                    url=media_url,
                    iiif_url=f"{iiif_base}/full/max/0/default.jpg" if iiif_base else None,
                    iiif_base=iiif_base,
                    iiif_manifest_url=(
                        f"{portal_api}/objects/{record_id}/iiif/manifest" if iiif_base else None
                    ),
                    license_uri=mf.license_uri,
                    rights_statement_label=license_label(mf.license_uri),
                    rights_holder=rights_holder_str,
                    rights_holder_uri=rights_holder_uri,
                    credit_line=mf.credit_line,
                    width=mf.width,
                    height=mf.height,
                )
            )

    return ExportRecordContext(
        record=summary,
        fields=fields,
        relations=relations,
        media=media,
        inbound_relations_omitted=omitted,
    )


async def resolve_record_id(db: AsyncSession, record_type: str, ref: str) -> uuid.UUID:
    """Record id from a UUID or an inventory number (idno, unique per record type)."""
    ref = ref.strip()
    try:
        return uuid.UUID(ref)
    except ValueError:
        pass
    model = _MODEL_MAP.get(record_type)
    if model is None:
        raise ValueError(f"Nicht unterstützter Datensatztyp: {record_type}")
    query = select(model.id).where(model.idno == ref)
    if hasattr(model, "deleted_at"):
        query = query.where(model.deleted_at.is_(None))
    record_id = (await db.execute(query)).scalar_one_or_none()
    if record_id is None:
        raise ValueError(f"Kein Datensatz mit Inventarnummer '{ref}' gefunden.")
    return uuid.UUID(str(record_id))


def index_context_is_stale(export_context: Any) -> bool:
    """True if an index copy must be rebuilt from the database before exporting it.

    That is the case when inbound relations were left out for size, and when the copy
    was written by an older Katalon (``schema_version`` below EXPORT_CONTEXT_VERSION):
    exporters would otherwise emit incomplete records until the next full reindex.
    """
    if not isinstance(export_context, dict):
        return False
    if export_context.get("inbound_relations_omitted"):
        return True
    return int(export_context.get("schema_version") or 0) < EXPORT_CONTEXT_VERSION


async def refresh_index_contexts(db: AsyncSession, hits: list[dict[str, Any]]) -> None:
    """Replace stale index copies of the export context with the full context from
    the database, in place (see index_context_is_stale)."""
    for hit in hits:
        source = hit.get("_source") or {}
        ec = source.get("export_context")
        if not index_context_is_stale(ec):
            continue
        record = ec.get("record") or {}
        try:
            full = await build_export_context_from_db(
                db, str(record.get("record_type")), uuid.UUID(str(record.get("id")))
            )
        except ValueError:
            logger.warning("Export context of %s could not be rebuilt", record.get("id"), exc_info=True)
            continue
        source["export_context"] = full.to_dict()
