# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import json
import logging
import uuid
from typing import TYPE_CHECKING, Any

import rdflib
from fastapi import Response
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.config import settings
from katalon.core.models import (
    Collection,
    Entity,
    MediaFile,
    Object,
    Occurrence,
    Place,
    Procedure,
    RecordSubtype,
    Relation,
    StorageLocation,
    Vocabulary,
    VocabularyTerm,
)

if TYPE_CHECKING:
    from fastapi import Request

    from katalon.core.models import User
from katalon.integrations.jsonld_format import build_jsonld_doc
from katalon.services.relation_service import resolve_relation_labels
from katalon.services.search_service import _extract_title

logger = logging.getLogger(__name__)

RECORD_MODEL_MAP: dict[str, tuple[type[Any], str]] = {
    "object": (Object, "object_type"),
    "entity": (Entity, "entity_type"),
    "place": (Place, "place_type"),
    "occurrence": (Occurrence, "occurrence_type"),
    "procedure": (Procedure, "procedure_type"),
    "collection": (Collection, "collection_type"),
    "storage_location": (StorageLocation, "storage_location_type"),
}


def get_canonical_base_url(request_base_url: str = "") -> str:
    """Resolve the canonical base URL, preferring KATALON_BASE_URL over request host."""
    configured = settings.katalon_base_url.strip().rstrip("/")
    if configured:
        return configured
    return request_base_url.rstrip("/") if request_base_url else ""


async def resolve_vocabulary_concepts(
    db: AsyncSession,
    terms: set[str],
    base_url: str = "",
) -> dict[str, dict[str, Any]]:
    """Resolve term strings to skos:Concept dictionaries with canonical URIs and labels."""
    if not terms:
        return {}

    stmt = (
        select(VocabularyTerm, Vocabulary)
        .join(Vocabulary, VocabularyTerm.vocabulary_id == Vocabulary.id)
        .where(VocabularyTerm.term.in_(terms))
    )
    result = await db.execute(stmt)
    rows = result.all()

    clean_base = base_url.rstrip("/") if base_url else ""
    concepts: dict[str, dict[str, Any]] = {}

    for term, vocab in rows:
        if term.uri:
            uri = term.uri
        elif vocab.canonical_uri:
            sep = "#" if "#" in vocab.canonical_uri else "/"
            uri = f"{vocab.canonical_uri.rstrip('/')}{sep}{term.term}"
        elif clean_base:
            uri = f"{clean_base}/portal/v1/vocabularies/{term.vocabulary_id}/terms/{term.id}"
        else:
            uri = f"urn:katalon:concept:{term.term}"

        concept_obj: dict[str, Any] = {
            "@type": "skos:Concept",
            "@id": uri,
        }

        if term.label and isinstance(term.label, dict):
            pref_labels = [
                {"@value": str(val), "@language": str(lang)}
                for lang, val in term.label.items()
                if val
            ]
            if len(pref_labels) == 1:
                concept_obj["skos:prefLabel"] = pref_labels[0]
            elif pref_labels:
                concept_obj["skos:prefLabel"] = pref_labels
            else:
                concept_obj["skos:prefLabel"] = term.term
        else:
            concept_obj["skos:prefLabel"] = term.term

        if term.exact_match_uris:
            concept_obj["skos:exactMatch"] = term.exact_match_uris

        concepts[term.term] = concept_obj

    return concepts


def extract_terms_from_metadata(metadata: dict[str, Any]) -> set[str]:
    """Scan metadata values for possible vocabulary term tokens."""
    terms: set[str] = set()
    for val in metadata.values():
        if isinstance(val, str) and val.strip():
            terms.add(val.strip())
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, str) and item.strip():
                    terms.add(item.strip())
    return terms


async def serialize_record_to_jsonld(
    db: AsyncSession,
    record_type: str,
    record: Any,
    base_url: str = "",
    mappings: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Serialize an ORM record into a complete JSON-LD CIDOC-CRM/LRMoo document."""
    record_id = record.id
    _, subtype_col = RECORD_MODEL_MAP[record_type]
    subtype = getattr(record, subtype_col, None)
    idno = getattr(record, "idno", None)
    md = record.metadata_ or {}

    subtype_label = None
    if subtype:
        st_res = await db.execute(
            select(RecordSubtype.label).where(
                RecordSubtype.primary_type == record_type,
                RecordSubtype.name == subtype,
            )
        )
        st_lbl = st_res.scalar_one_or_none()
        if isinstance(st_lbl, dict):
            subtype_label = st_lbl.get("de") or st_lbl.get("en") or subtype
        elif isinstance(st_lbl, str):
            subtype_label = st_lbl

    title = _extract_title(md) or idno or str(record_id)
    # Resolve vocabulary terms to skos:Concept
    terms = extract_terms_from_metadata(md)
    vocab_concepts = await resolve_vocabulary_concepts(db, terms, base_url=base_url)

    # Load relations involving this record
    rel_stmt = (
        select(Relation)
        .where(
            or_(
                (Relation.from_type == record_type) & (Relation.from_id == record_id),
                (Relation.to_type == record_type) & (Relation.to_id == record_id),
            )
        )
        .order_by(Relation.created_at)
    )
    rel_rows = list((await db.execute(rel_stmt)).scalars().all())
    labels = await resolve_relation_labels(db, rel_rows)

    target_ids_by_type: dict[str, set[uuid.UUID]] = {}
    for r in rel_rows:
        is_outgoing = r.from_type == record_type and r.from_id == record_id
        t_type = r.to_type if is_outgoing else r.from_type
        t_id = r.to_id if is_outgoing else r.from_id
        target_ids_by_type.setdefault(t_type, set()).add(t_id)

    subtypes: dict[tuple[str, uuid.UUID], str | None] = {}
    for t_type, ids in target_ids_by_type.items():
        if t_type in RECORD_MODEL_MAP:
            m_cls, s_col = RECORD_MODEL_MAP[t_type]
            res = await db.execute(select(m_cls.id, getattr(m_cls, s_col)).where(m_cls.id.in_(ids)))
            for row_id, s_val in res.all():
                subtypes[(t_type, row_id)] = s_val
    rel_type_names = {r.relation_type for r in rel_rows if r.relation_type}
    rel_type_uris: dict[str, str] = {}
    if rel_type_names:
        rt_stmt = (
            select(VocabularyTerm.term, VocabularyTerm.uri)
            .join(Vocabulary, Vocabulary.id == VocabularyTerm.vocabulary_id)
            .where(Vocabulary.kind == "relation", VocabularyTerm.term.in_(rel_type_names))
        )
        rt_rows = (await db.execute(rt_stmt)).all()
        for term_code, term_uri in rt_rows:
            if term_uri and term_uri.strip():
                rel_type_uris[term_code] = term_uri.strip()

    rel_dicts: list[dict[str, Any]] = []
    for r in rel_rows:
        is_outgoing = r.from_type == record_type and r.from_id == record_id
        target_type = r.to_type if is_outgoing else r.from_type
        target_id = r.to_id if is_outgoing else r.from_id
        target_label = labels.get((target_type, target_id))
        target_subtype = subtypes.get((target_type, target_id))
        rel_prop = rel_type_uris.get(r.relation_type) or r.relation_type

        rel_dicts.append({
            "from_type": r.from_type,
            "from_id": str(r.from_id),
            "to_type": r.to_type,
            "to_id": str(r.to_id),
            "target_type": target_type,
            "target_id": str(target_id),
            "target_subtype": target_subtype,
            "label": target_label,
            "relation_type": rel_prop,
        })
    # Place geom point
    geo_point = None
    if record_type == "place" and hasattr(record, "lon") and hasattr(record, "lat"):
        if record.lon is not None and record.lat is not None:
            geo_point = (float(record.lon), float(record.lat))

    # Media files for Object
    media_dicts: list[dict[str, Any]] = []
    if record_type == "object":
        media_stmt = (
            select(MediaFile)
            .where(MediaFile.object_id == record_id, MediaFile.is_public.is_(True))
            .order_by(MediaFile.is_primary.desc(), MediaFile.created_at)
        )
        media_rows = list((await db.execute(media_stmt)).scalars().all())
        for m in media_rows:
            media_dicts.append({
                "id": str(m.id),
                "filename": m.filename,
                "manifest_uri": (
                    f"{base_url.rstrip('/')}/iiif/3/{m.id}/manifest.json" if base_url else None
                ),
            })

    return build_jsonld_doc(
        record_type=record_type,
        record_id=str(record_id),
        title=title,
        idno=idno,
        subtype=subtype,
        subtype_label=subtype_label,
        metadata=md,
        relations=rel_dicts,
        vocab_concepts=vocab_concepts,
        mappings=mappings,
        base_url=base_url,
        media_files=media_dicts,
        geo_point=geo_point,
    )


async def export_single_record(
    db: AsyncSession,
    record_type: str,
    record_id: uuid.UUID,
    format: str = "jsonld",
    base_url: str = "",
) -> tuple[str, str, str]:
    """Export single record as JSON-LD or Turtle RDF.

    Returns (payload, media_type, filename).
    """
    if record_type not in RECORD_MODEL_MAP:
        raise ValueError(f"Unbekannter Datensatztyp: {record_type}")

    model, _ = RECORD_MODEL_MAP[record_type]
    query = select(model).where(model.id == record_id)
    if hasattr(model, "deleted_at"):
        query = query.where(model.deleted_at.is_(None))
    record = (await db.execute(query)).scalar_one_or_none()
    if not record:
        raise ValueError(f"{record_type.capitalize()} nicht gefunden")

    doc = await serialize_record_to_jsonld(db, record_type, record, base_url=base_url)

    norm_format = (format or "jsonld").lower().strip()
    if norm_format in ("ttl", "turtle"):
        g = rdflib.Graph()
        g.parse(data=json.dumps(doc), format="json-ld")
        content = g.serialize(format="turtle")
        return content, "text/turtle; charset=utf-8", f"{record_type}_{record_id}.ttl"

    # Default: jsonld / json-ld
    content = json.dumps(doc, indent=2, ensure_ascii=False)
    return content, "application/ld+json; charset=utf-8", f"{record_type}_{record_id}.jsonld"


async def handle_single_record_export(
    record_type: str,
    record_id: uuid.UUID,
    db: AsyncSession,
    request: Request | None = None,
    *,
    current_user: User | None = None,
    format_param: str | None = None,
    accept_header: str | None = None,
) -> Response:
    from fastapi import HTTPException, Response

    from katalon.core.dependencies import has_record_permission
    from katalon.core.visibility import ensure_publicly_visible

    norm_type = record_type.lower().strip()
    if norm_type.endswith("s") and norm_type[:-1] in RECORD_MODEL_MAP:
        norm_type = norm_type[:-1]

    if norm_type not in RECORD_MODEL_MAP:
        raise HTTPException(status_code=404, detail=f"Unbekannter Datensatztyp: {record_type}")

    model, _ = RECORD_MODEL_MAP[norm_type]
    query = select(model).where(model.id == record_id)
    if hasattr(model, "deleted_at"):
        query = query.where(model.deleted_at.is_(None))
    record = (await db.execute(query)).scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail=f"{norm_type.capitalize()} nicht gefunden")

    visibility_user = (
        current_user
        if current_user and await has_record_permission(db, current_user, norm_type, "read")
        else None
    )
    ensure_publicly_visible(record, visibility_user, f"{norm_type.capitalize()} nicht gefunden")

    format_choice = "jsonld"
    if format_param:
        fmt = format_param.lower().strip()
        if fmt in ("ttl", "turtle"):
            format_choice = "turtle"
        elif fmt in ("jsonld", "json-ld"):
            format_choice = "jsonld"
    elif accept_header:
        if "text/turtle" in accept_header:
            format_choice = "turtle"
        elif "application/ld+json" in accept_header:
            format_choice = "jsonld"

    raw_request_base = str(request.base_url) if request else ""
    base_url = get_canonical_base_url(raw_request_base)
    content, media_type, filename = await export_single_record(
        db, norm_type, record_id, format=format_choice, base_url=base_url
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
