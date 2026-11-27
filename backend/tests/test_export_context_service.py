# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from katalon.core.models import FieldDefinition, MediaFile, Object, Relation
from katalon.integrations.lido_format import LidoFormat
from katalon.integrations.metadata_format import (
    CompiledMappingSet,
    ExportMediaItem,
    ExportRecordContext,
    ExportRecordSummary,
    ExportRelation,
    MappingSpec,
    SourceKind,
)
from katalon.integrations.oai_dc_format import OaiDcFormat
from katalon.services import export_context_service, search_service

# ---------------------------------------------------------------------------
# Unit tests: Serialization & Fallbacks
# ---------------------------------------------------------------------------


def test_export_record_context_serialization_roundtrip() -> None:
    rec_id = str(uuid.uuid4())
    summary = ExportRecordSummary(
        id=rec_id,
        idno="OBJ-100",
        record_type="object",
        target_subtype="postcard",
        title="Blick auf den Markt",
        status="public",
        created_at="2026-01-01T12:00:00Z",
        updated_at="2026-02-01T12:00:00Z",
        canonical_url=f"https://example.org/object/{rec_id}",
    )
    rel = ExportRelation(
        id=str(uuid.uuid4()),
        direction="outbound",
        relation_type="photographer",
        target_type="entity",
        target_id=str(uuid.uuid4()),
        target_label="Max Mustermann",
        target_idno="GND-12345",
        target_values={"preferred_name": "Mustermann, Max"},
    )
    media = ExportMediaItem(
        id=str(uuid.uuid4()),
        filename="postcard_front.jpg",
        mime_type="image/jpeg",
        role="primary",
        is_primary=True,
        is_public=True,
        url="https://example.org/media/postcard_front.jpg",
        iiif_url="https://example.org/iiif/3/1/full/max/0/default.jpg",
        license_uri="https://creativecommons.org/publicdomain/zero/1.0/",
        rights_holder="Stadtarchiv",
    )
    ctx = ExportRecordContext(
        record=summary,
        fields={"description": "Historische Aufnahme", "keywords": ["Markt", "Kirche"]},
        relations=[rel],
        media=[media],
    )

    doc_dict = {"_id": rec_id, "_source": {"export_context": ctx.to_dict()}}
    loaded = ExportRecordContext.from_hit(doc_dict)

    assert loaded.record.id == rec_id
    assert loaded.record.title == "Blick auf den Markt"
    assert loaded.fields["description"] == "Historische Aufnahme"
    assert len(loaded.relations) == 1
    assert loaded.relations[0].target_label == "Max Mustermann"
    assert len(loaded.media) == 1
    assert loaded.media[0].filename == "postcard_front.jpg"
    assert loaded.media[0].is_primary is True


def test_export_record_context_from_hit_fallback() -> None:
    rec_id = str(uuid.uuid4())
    raw_hit = {
        "_id": rec_id,
        "_source": {
            "record_type": "object",
            "title": "Minimales Objekt",
            "idno": "MIN-01",
            "metadata": {"custom_field": "Wert"},
        },
    }
    ctx = ExportRecordContext.from_hit(raw_hit)
    assert ctx.record.id == rec_id
    assert ctx.record.title == "Minimales Objekt"
    assert ctx.record.idno == "MIN-01"
    assert ctx.fields["custom_field"] == "Wert"
    assert ctx.relations == []
    assert ctx.media == []


# ---------------------------------------------------------------------------
# Security Invariants in build_export_context_from_db
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_export_context_from_db_security_filtering(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(export_context_service.settings, "cantaloupe_public_url", "")
    rec_id = uuid.uuid4()
    mock_obj = MagicMock(spec=Object)
    mock_obj.id = rec_id
    mock_obj.idno = "SEC-001"
    mock_obj.title = "Sicherheits-Objekt"
    mock_obj.object_type = "postcard"
    mock_obj.status = "public"
    mock_obj.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    mock_obj.updated_at = datetime(2026, 1, 2, tzinfo=UTC)
    mock_obj.deleted_at = None
    mock_obj.metadata_ = {
        "public_title": "Öffentlicher Titel",
        "internal_notes": "Streng vertrauliche Kuratoren-Notiz",
    }

    # Public field vs internal field
    pub_field = MagicMock(spec=FieldDefinition)
    pub_field.name = "public_title"
    pub_field.is_public = True
    pub_field.is_deleted = False

    # Relations:
    # 1. Public entity relation
    entity_id = uuid.uuid4()
    rel_entity = MagicMock(spec=Relation)
    rel_entity.id = uuid.uuid4()
    rel_entity.from_type = "object"
    rel_entity.from_id = rec_id
    rel_entity.to_type = "entity"
    rel_entity.to_id = entity_id
    rel_entity.relation_type = "photographer"
    rel_entity.metadata_ = {}

    mock_entity = MagicMock()
    mock_entity.id = entity_id
    mock_entity.title = "Öffentlicher Fotograf"
    mock_entity.idno = "GND-999"
    mock_entity.status = "public"
    mock_entity.deleted_at = None
    mock_entity.metadata_ = {"name": "Öffentlicher Fotograf"}
    mock_entity.entity_type = "ind"

    # 2. Excluded relation: storage_location (internal logistics!)
    rel_storage = MagicMock(spec=Relation)
    rel_storage.id = uuid.uuid4()
    rel_storage.from_type = "object"
    rel_storage.from_id = rec_id
    rel_storage.to_type = "storage_location"
    rel_storage.to_id = uuid.uuid4()
    rel_storage.relation_type = "current_location"

    # Media:
    # 1. Public media
    mf_pub = MagicMock(spec=MediaFile)
    mf_pub.id = uuid.uuid4()
    mf_pub.filename = "public_scan.jpg"
    mf_pub.mime_type = "image/jpeg"
    mf_pub.is_primary = True
    mf_pub.is_public = True
    mf_pub.iiif_storage_key = "iiif/scan"
    mf_pub.license_uri = "https://creativecommons.org/publicdomain/zero/1.0/"
    mf_pub.rights_holder = {"name": "Museum"}
    mf_pub.credit_line = "Veröffentlichung genehmigt."
    mf_pub.width = 1200
    mf_pub.height = 800
    mf_pub.status = "ready"
    mf_pub.storage_key = "originals/scan.jpg"

    # 2. Non-public media (is_public=False)
    mf_priv = MagicMock(spec=MediaFile)
    mf_priv.id = uuid.uuid4()
    mf_priv.filename = "internal_condition_report.pdf"
    mf_priv.mime_type = "application/pdf"
    mf_priv.is_primary = False
    mf_priv.is_public = False
    mf_priv.rights_holder = None

    mock_db = AsyncMock()

    # Dispatch get() calls
    async def _mock_get(model: Any, ident: Any) -> Any:
        if model == Object and ident == rec_id:
            return mock_obj
        if ident == entity_id:
            return mock_entity
        return None

    mock_db.get = AsyncMock(side_effect=_mock_get)

    # Dispatch execute() calls for relations and media
    res_rels = MagicMock()
    res_rels.scalars.return_value.all.return_value = [rel_entity, rel_storage]

    res_media = MagicMock()
    res_media.scalars.return_value.all.return_value = [mf_pub]  # DB query filters is_public=True

    res_no_subtype = MagicMock()
    res_no_subtype.scalar_one_or_none.return_value = None

    def _mock_exec(stmt: Any) -> Any:
        s = str(stmt)
        if "relations.from_type = " in s:
            return res_rels
        if "count(" in s:
            res_count = MagicMock()
            res_count.scalar_one.return_value = 0
            return res_count
        if "FROM entities" in s:
            res_entities = MagicMock()
            res_entities.scalars.return_value = [mock_entity]
            return res_entities
        if "relations.to_type = " in s:
            res_empty = MagicMock()
            res_empty.scalars.return_value.all.return_value = []
            return res_empty
        if "media_files" in s:
            return res_media
        if "record_subtypes" in s:
            return res_no_subtype
        res = MagicMock()
        res.scalars.return_value.all.return_value = []
        return res

    mock_db.execute = AsyncMock(side_effect=_mock_exec)

    # Mock public metadata service helpers
    orig_load = export_context_service.load_public_fields
    orig_filter = export_context_service.filter_public_metadata

    try:
        export_context_service.load_public_fields = AsyncMock(return_value=[pub_field])
        export_context_service.filter_public_metadata = MagicMock(
            return_value={"public_title": "Öffentlicher Titel"}
        )

        ctx = await export_context_service.build_export_context_from_db(
            mock_db, "object", rec_id, base_url="https://katalon.example.org"
        )

        # Invariant 1: Interne Felder sind ausgeschlossen
        assert "internal_notes" not in ctx.fields
        assert ctx.fields.get("public_title") == "Öffentlicher Titel"

        # Invariant 2: storage_location ist strikt aus Relationen ausgeschlossen
        rel_target_types = {r.target_type for r in ctx.relations}
        assert "storage_location" not in rel_target_types
        assert "entity" in rel_target_types
        assert len(ctx.relations) == 1
        assert ctx.relations[0].target_label == "Öffentlicher Fotograf"

        # Invariant 3: Nicht-öffentliche Medien sind ausgeschlossen
        media_filenames = {m.filename for m in ctx.media}
        assert "internal_condition_report.pdf" not in media_filenames
        assert "public_scan.jpg" in media_filenames
        media = ctx.media[0]
        # Cantaloupe identifies images by the encoded IIIF storage key, not the media UUID.
        assert media.iiif_base == "https://katalon.example.org/iiif/3/iiif%2Fscan"
        assert media.iiif_url == "https://katalon.example.org/iiif/3/iiif%2Fscan/full/max/0/default.jpg"
        assert media.credit_line == "Veröffentlichung genehmigt."
        assert media.rights_statement_label == "CC0 1.0"
        assert ctx.relations[0].target_subtype == "ind"
        assert len(ctx.media) == 1
        assert ctx.media[0].is_primary is True
        assert "iiif" in (ctx.media[0].iiif_url or "")

    finally:
        export_context_service.load_public_fields = orig_load
        export_context_service.filter_public_metadata = orig_filter


# ---------------------------------------------------------------------------
# Format Renderer Integration with ExportRecordContext
# ---------------------------------------------------------------------------


def test_render_with_relations_and_media_sources() -> None:
    rec_id = str(uuid.uuid4())
    summary = ExportRecordSummary(
        id=rec_id,
        idno="CARD-42",
        record_type="object",
        title="Postkarte Schloss",
        status="public",
        canonical_url="https://katalon.example.org/object/CARD-42",
    )
    rel = ExportRelation(
        id=str(uuid.uuid4()),
        direction="outbound",
        relation_type="photographer",
        target_type="entity",
        target_id=str(uuid.uuid4()),
        target_label="Paul Barbier",
    )
    media = ExportMediaItem(
        id=str(uuid.uuid4()),
        filename="card.jpg",
        mime_type="image/jpeg",
        role="primary",
        url="https://katalon.example.org/media/card.jpg",
    )
    ctx = ExportRecordContext(
        record=summary,
        fields={"title": "Postkarte Schloss"},
        relations=[rel],
        media=[media],
    )

    mapping_set = CompiledMappingSet(
        format_key="oai_dc",
        record_type="object",
        rules=[
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "title"},
                target_key="dc:title",
            ),
            MappingSpec(
                source_kind=SourceKind.RELATION,
                source_config={"relation_type": "photographer"},
                target_key="dc:creator",
                settings={"prefix": "Fotograf: "},
            ),
            MappingSpec(
                source_kind=SourceKind.RECORD,
                source_config={"property": "canonical_url"},
                target_key="dc:identifier",
            ),
            MappingSpec(
                source_kind=SourceKind.CONSTANT,
                source_config={"value": "Historische Sammlung"},
                target_key="dc:source",
            ),
        ],
    )

    fmt = OaiDcFormat()
    el = fmt.render(ctx, mapping_set)
    xml_str = ET.tostring(el, encoding="unicode")

    assert "<dc:title>Postkarte Schloss</dc:title>" in xml_str
    assert "<dc:creator>Fotograf: Paul Barbier</dc:creator>" in xml_str
    assert "<dc:identifier>https://katalon.example.org/object/CARD-42</dc:identifier>" in xml_str
    assert "<dc:source>Historische Sammlung</dc:source>" in xml_str


def test_lido_render_with_export_record_context_relation() -> None:
    rec_id = str(uuid.uuid4())
    summary = ExportRecordSummary(
        id=rec_id,
        idno="LIDO-01",
        record_type="object",
        title="Historische Postkarte",
        status="public",
    )
    rel = ExportRelation(
        id=str(uuid.uuid4()),
        direction="outbound",
        relation_type="photographer",
        target_type="entity",
        target_id=str(uuid.uuid4()),
        target_label="Paul Barbier",
    )
    ctx = ExportRecordContext(
        record=summary,
        fields={"title": "Historische Postkarte"},
        relations=[rel],
        media=[],
    )

    mapping_set = CompiledMappingSet(
        format_key="lido",
        record_type="object",
        rules=[
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "title"},
                target_key="lido:objectIdentificationWrap/lido:titleWrap/lido:titleSet/lido:appellationValue",
            ),
            MappingSpec(
                source_kind=SourceKind.RELATION,
                source_config={"relation_type": "photographer"},
                target_key="lido:eventWrap/lido:eventSet/lido:event/lido:eventActor/lido:actorInRole/lido:actor/lido:nameActorSet/lido:appellationValue",
            ),
        ],
    )

    fmt = LidoFormat()
    el = fmt.render(ctx, mapping_set)
    xml_str = ET.tostring(el, encoding="unicode")

    assert "Historische Postkarte" in xml_str
    assert "Paul Barbier" in xml_str


# ---------------------------------------------------------------------------
# Search service build_index_doc integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_index_doc_embeds_export_context() -> None:
    rec_id = uuid.uuid4()
    mock_obj = MagicMock(spec=Object)
    mock_obj.id = rec_id
    mock_obj.idno = "IDX-001"
    mock_obj.title = "Index Test"
    mock_obj.object_type = "postcard"
    mock_obj.status = "public"
    mock_obj.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    mock_obj.updated_at = datetime(2026, 1, 2, tzinfo=UTC)
    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = []
    mock_res.all.return_value = []
    mock_db.execute.return_value = mock_res

    orig_build = export_context_service.build_export_context_from_db
    try:
        mock_ctx = ExportRecordContext(
            record=ExportRecordSummary(
                id=str(rec_id),
                record_type="object",
                status="public",
                title="Index Test",
            ),
            fields={"title": "Index Test"},
            relations=[],
            media=[],
        )
        export_context_service.build_export_context_from_db = AsyncMock(return_value=mock_ctx)

        # In search_service.build_index_doc, db is passed
        doc = await search_service.build_index_doc("object", mock_obj, db=mock_db)

        assert "export_context" in doc
        ec = doc["export_context"]
        assert ec["record"]["id"] == str(rec_id)
        assert ec["fields"]["title"] == "Index Test"
    finally:
        export_context_service.build_export_context_from_db = orig_build


def test_record_title_ignores_internal_title_field() -> None:
    obj = Object(id=uuid.uuid4(), idno="OBJ-7", metadata_={"title": "Geheimer Spender"})
    public = FieldDefinition(name="title", field_type="text", is_public=True)
    assert export_context_service._record_title(obj, "object", [public]) == "Geheimer Spender"
    assert export_context_service._record_title(obj, "object", []) == "OBJ-7"


@pytest.mark.asyncio
async def test_build_export_context_populates_only_public_place_ancestors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from katalon.services.place_service import PlaceNode

    obj_id = uuid.uuid4()
    country_id = uuid.uuid4()
    region_id = uuid.uuid4()
    site_id = uuid.uuid4()
    hidden_parent_id = uuid.uuid4()
    isolated_site_id = uuid.uuid4()

    mock_obj = MagicMock(spec=Object)
    mock_obj.id = obj_id
    mock_obj.idno = "F-1"
    mock_obj.title = "Faustkeil"
    mock_obj.object_type = None
    mock_obj.status = "public"
    mock_obj.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    mock_obj.updated_at = datetime(2026, 1, 2, tzinfo=UTC)
    mock_obj.deleted_at = None
    mock_obj.metadata_ = {}

    rel_public_chain = MagicMock(spec=Relation)
    rel_public_chain.id = uuid.uuid4()
    rel_public_chain.from_type = "object"
    rel_public_chain.from_id = obj_id
    rel_public_chain.to_type = "place"
    rel_public_chain.to_id = site_id
    rel_public_chain.relation_type = "fundort"
    rel_public_chain.metadata_ = {}

    rel_hidden_parent = MagicMock(spec=Relation)
    rel_hidden_parent.id = uuid.uuid4()
    rel_hidden_parent.from_type = "object"
    rel_hidden_parent.from_id = obj_id
    rel_hidden_parent.to_type = "place"
    rel_hidden_parent.to_id = isolated_site_id
    rel_hidden_parent.relation_type = "fundort"
    rel_hidden_parent.metadata_ = {}

    mock_site = MagicMock()
    mock_site.id = site_id
    mock_site.title = "La Madeleine"
    mock_site.idno = "P-3"
    mock_site.status = "public"
    mock_site.deleted_at = None
    mock_site.metadata_ = {"label": "La Madeleine"}
    mock_site.place_type = None

    mock_isolated = MagicMock()
    mock_isolated.id = isolated_site_id
    mock_isolated.title = "Fundstelle X"
    mock_isolated.idno = "P-4"
    mock_isolated.status = "public"
    mock_isolated.deleted_at = None
    mock_isolated.metadata_ = {"label": "Fundstelle X"}
    mock_isolated.place_type = None

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=mock_obj)

    def _mock_exec(stmt: Any) -> Any:
        s = str(stmt)
        if "relations.from_type = " in s:
            res = MagicMock()
            res.scalars.return_value.all.return_value = [rel_public_chain, rel_hidden_parent]
            return res
        if "count(" in s:
            res = MagicMock()
            res.scalar_one.return_value = 0
            return res
        if "FROM places" in s:
            res = MagicMock()
            res.scalars.return_value = [mock_site, mock_isolated]
            return res
        res = MagicMock()
        res.scalars.return_value.all.return_value = []
        res.all.return_value = []
        return res

    mock_db.execute = AsyncMock(side_effect=_mock_exec)
    monkeypatch.setattr(export_context_service, "load_public_fields", AsyncMock(return_value=[]))
    monkeypatch.setattr(export_context_service, "filter_public_metadata", MagicMock(return_value={}))
    monkeypatch.setattr(export_context_service, "load_hidden_relation_targets", AsyncMock(return_value=set()))

    # Portal visibility: hidden_parent_id is absent from public_only=True nodes,
    # so isolated_site_id has no visible ancestors while site_id gets [Frankreich, Dordogne].
    public_nodes = {
        country_id: PlaceNode(country_id, None, "Frankreich"),
        region_id: PlaceNode(region_id, country_id, "Dordogne"),
        site_id: PlaceNode(site_id, region_id, "La Madeleine"),
        isolated_site_id: PlaceNode(isolated_site_id, hidden_parent_id, "Fundstelle X"),
    }
    load_nodes_mock = AsyncMock(return_value=public_nodes)
    monkeypatch.setattr(export_context_service, "load_place_chains", load_nodes_mock)

    ctx = await export_context_service.build_export_context_from_db(
        mock_db, "object", obj_id, via_relation_types=set()
    )

    load_nodes_mock.assert_awaited_once_with(
        mock_db, {site_id, isolated_site_id}, public_only=True
    )
    by_id = {r.target_id: r for r in ctx.relations}
    assert by_id[str(site_id)].target_ancestors == ["Frankreich", "Dordogne"]
    assert by_id[str(isolated_site_id)].target_ancestors == []
