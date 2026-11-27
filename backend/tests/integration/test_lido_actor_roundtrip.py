# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""End-to-end verification of LIDO eventActor import, resolution, and LIDO export.

Exercises the actual XML parser (XmlFormat), mapping coercion (apply_mapping),
relation resolution (resolve_relations), relation syncing (sync_schema_relations),
public export context building (build_export_context_from_db), and LIDO 1.0
rendering/XSD validation against ``lido_ddb_os_ub_0031153.xml``.
"""

from __future__ import annotations

import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest
import yaml
from lxml import etree
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from katalon.core.models import Entity, FieldDefinition, Object
from katalon.integrations.lido.builder import LIDO_NS
from katalon.integrations.lido.validator import validate_lido_xml
from katalon.integrations.lido_format import LidoFormat
from katalon.integrations.metadata_format import CompiledMappingSet, MappingSpec, SourceKind
from katalon.services.export_context_service import build_export_context_from_db
from katalon.services.import_resolution import resolve_relations
from katalon.services.importer.formats.xml_format import XmlFormat
from katalon.services.importer_service import apply_mapping
from katalon.services.relation_service import sync_schema_relations

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
LIDO_XML = FIXTURES / "lido_ddb_os_ub_0031153.xml"
DEMO_SCHEMA_YAML = FIXTURES / "lido_demo_schema.yaml"
DDB_MAPPING_YAML = FIXTURES / "lido_ddb_mapping.yaml"

NS = {"lido": LIDO_NS}
L = f"{{{LIDO_NS}}}"

# Selectors produced by XmlFormat on a {http://www.lido-schema.org}lido record
SEL_IDNO = f"{L}administrativeMetadata/{L}recordWrap/{L}recordID"
SEL_TITLE = (
    f"{L}descriptiveMetadata/{L}objectIdentificationWrap/{L}titleWrap/"
    f"{L}titleSet/{L}appellationValue"
)
SEL_ACTOR_NAME = (
    f"{L}descriptiveMetadata/{L}eventWrap/{L}eventSet/{L}event/{L}eventActor/"
    f"{L}actorInRole/{L}actor/{L}nameActorSet/{L}appellationValue"
)
SEL_ACTOR_ROLE = (
    f"{L}descriptiveMetadata/{L}eventWrap/{L}eventSet/{L}event/{L}eventActor/"
    f"{L}actorInRole/{L}roleActor/{L}term"
)
SEL_ACTOR_ID = (
    f"{L}descriptiveMetadata/{L}eventWrap/{L}eventSet/{L}event/{L}eventActor/"
    f"{L}actorInRole/{L}actor/{L}actorID"
)
SEL_ACTOR_TYPE = (
    f"{L}descriptiveMetadata/{L}eventWrap/{L}eventSet/{L}event/{L}eventActor/"
    f"{L}actorInRole/{L}actor@lido:type"
)
SEL_EVENT_TYPE = f"{L}descriptiveMetadata/{L}eventWrap/{L}eventSet/{L}event/{L}eventType/{L}term"

# Selectors produced by XmlFormat on a {http://www.lido-schema.org}actor record (two-pass)
SEL_SUB_ACTOR_NAME = f"{L}nameActorSet/{L}appellationValue"
SEL_SUB_ACTOR_ID = f"{L}actorID"
SEL_SUB_ACTOR_TYPE = "@lido:type"


def _lido_mapping_set(
    *,
    events: list[dict[str, str]],
    actor_rules: list[MappingSpec],
    actor_id_fields: list[dict[str, str]] | None = None,
    actor_types: dict[str, str] | None = None,
) -> CompiledMappingSet:
    ddb_cfg = yaml.safe_load(DDB_MAPPING_YAML.read_text(encoding="utf-8"))["institution_config"]
    config: dict[str, Any] = {
        "isil": ddb_cfg["isil"],
        "institution_name": ddb_cfg["institution_name"],
        "website": ddb_cfg["website"],
        "location": ddb_cfg["location"],
        "lido_events": events,
    }
    if actor_id_fields is not None:
        config["actor_id_fields"] = actor_id_fields
    if actor_types is not None:
        config["actor_types"] = actor_types
    return CompiledMappingSet(
        format_key="lido",
        record_type="object",
        rules=[
            MappingSpec(
                source_kind=SourceKind.FIELD,
                source_config={"field_name": "title"},
                target_key=(
                    "lido:objectIdentificationWrap/lido:titleWrap/"
                    "lido:titleSet/lido:appellationValue"
                ),
                sort_order=10,
            ),
            MappingSpec(
                source_kind=SourceKind.CONSTANT,
                source_config={"value": "Postkarte"},
                target_key="lido:objectClassificationWrap/lido:objectWorkTypeWrap/lido:objectWorkType",
                sort_order=20,
            ),
            *actor_rules,
        ],
        institution_config=config,
    )


async def _ensure_field(
    session: AsyncSession,
    *,
    target_type: str,
    name: str,
    label_de: str,
    field_type: str,
    is_repeatable: bool = False,
    settings: dict[str, Any] | None = None,
) -> FieldDefinition:
    existing = (
        await session.execute(
            select(FieldDefinition).where(
                FieldDefinition.target_type == target_type,
                FieldDefinition.target_subtype.is_(None),
                FieldDefinition.name == name,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    fd = FieldDefinition(
        target_type=target_type,
        name=name,
        label={"de": label_de},
        field_type=field_type,
        is_repeatable=is_repeatable,
        is_public=True,
        settings=settings or {},
    )
    session.add(fd)
    await session.flush()
    return fd


def _single_actor_only_event_xml() -> bytes:
    """Copy of lido_ddb_os_ub_0031153.xml keeping only the actor-only creation event."""
    root = etree.fromstring(LIDO_XML.read_bytes())
    event_wrap = root.find(f".//{L}eventWrap")
    assert event_wrap is not None
    for event_set in list(event_wrap.findall(f"{L}eventSet")):
        term = event_set.findtext(f"{L}event/{L}eventType/{L}term")
        if term != "Geistige Schöpfung":
            event_wrap.remove(event_set)
    return bytes(etree.tostring(root, encoding="utf-8", xml_declaration=True))


@pytest.mark.asyncio
async def test_schema_import_yaml_accepts_entity_actor_recipe_extension(
    async_client: Any, auth_headers: dict[str, str]
) -> None:
    """Extending lido_demo_schema.yaml with an entity relation field and normdata URL field validates."""
    base = yaml.safe_load(DEMO_SCHEMA_YAML.read_text(encoding="utf-8"))
    base["relation_types"].append(
        {
            "term": "beteiligt",
            "label": {"de": "Beteiligt", "en": "Involved"},
            "inverse_label": {"de": "Beteiligt an", "en": "Involved in"},
            "applies_from": ["object"],
            "applies_to": ["entity"],
        }
    )
    object_schema = next(doc for doc in base["schemas"] if doc["target_type"] == "object")
    object_schema["fields"].append(
        {
            "name": "beteiligte",
            "label": {"de": "Beteiligte", "en": "Involved actors"},
            "field_type": "relation",
            "is_repeatable": True,
            "settings": {
                "target_type": "entity",
                "relation_type_vocab": "relation_types",
                "fixed_relation_type": "beteiligt",
            },
        }
    )
    base["schemas"].append(
        {
            "target_type": "entity",
            "fields": [
                {
                    "name": "normdaten",
                    "label": {"de": "Normdaten-URIs", "en": "Authority URIs"},
                    "field_type": "url",
                    "is_repeatable": True,
                }
            ],
        }
    )

    payload = yaml.safe_dump(base, allow_unicode=True).encode("utf-8")
    response = await async_client.post(
        "/v1/schema/import",
        headers=auth_headers,
        params={"dry_run": "true"},
        files={"file": ("schema.yaml", payload, "application/x-yaml")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["errors"] == []


@pytest.mark.asyncio
async def test_single_pass_lido_actor_import_flattens_events_drops_ids_and_hides_drafts(
    app: Any,
) -> None:
    """Single-pass lido:lido import with on_missing=create exposes four concrete gaps on the fixture."""
    from katalon.database import AsyncSessionLocal

    xml_bytes = LIDO_XML.read_bytes()
    rows = list(XmlFormat().parse_flat(xml_bytes, record_xpath=f"{L}lido"))
    assert len(rows) == 1
    row = rows[0]

    # Gap 1: XmlFormat collapses both eventSets (Herstellung + Geistige Schöpfung) into one list.
    assert row[SEL_EVENT_TYPE] == ["Herstellung", "Geistige Schöpfung", "Gebrauch"]
    assert row[SEL_ACTOR_NAME] == [
        "Verlag des Vereins für das Deutschtum im Ausland",
        "Novitas Verlag Otto Kellner",
        "Faber",
        "Paul Hey",
    ]
    assert row[SEL_ACTOR_ROLE] == [
        "Verlag, Herausgeber",
        "Verlag, Herausgeber",
        "Verlag, Herausgeber",
        "Maler / Zeichner / Illustrator",
    ]
    # Gap 2a: actorID has only 2 entries (both belonging to Paul Hey), unaligned with the 4 actors.
    assert row[SEL_ACTOR_ID] == [
        "https://d-nb.info/gnd/116785861",
        "http://www.wikidata.org/entity/Q2060171",
    ]
    assert row[SEL_ACTOR_TYPE] == [
        "http://terminology.lido-schema.org/lido00164",
        "http://terminology.lido-schema.org/lido00164",
        "http://terminology.lido-schema.org/lido00164",
        "http://terminology.lido-schema.org/lido00163",
    ]

    suffix = uuid.uuid4().hex[:8]
    rel_field_name = f"beteiligte_{suffix}"
    rel_type = f"creator_{suffix}"

    async with AsyncSessionLocal() as session:
        title_fd = await _ensure_field(
            session, target_type="object", name="title", label_de="Titel", field_type="text"
        )
        rel_fd = await _ensure_field(
            session,
            target_type="object",
            name=rel_field_name,
            label_de="Beteiligte",
            field_type="relation",
            is_repeatable=True,
            settings={"target_type": "entity", "fixed_relation_type": rel_type},
        )

        field_defs = {"title": title_fd, rel_field_name: rel_fd}
        mapping = {
            SEL_IDNO: "__idno__",
            SEL_TITLE: "title",
            SEL_ACTOR_NAME: rel_field_name,
        }
        records, idnos = apply_mapping(rows, mapping, field_defs)
        report = await resolve_relations(
            session,
            field_defs,
            records,
            {rel_field_name: {"lookup": "label", "on_missing": "create"}},
        )
        assert report.row_errors == {}
        assert len(report.created_records) == 4

        created_entities = [rec for _t, rec in report.created_records]
        # Gap 2a & 3 & 4: Created entities are drafts with only a label, no actorIDs and no subtype.
        for ent in created_entities:
            assert ent.status == "draft"
            assert set(ent.metadata_.keys()) == {"label"}
            assert ent.entity_type is None

        obj = Object(idno=f"{idnos[0]}_{suffix}", metadata_=records[0], status="public")
        session.add(obj)
        await session.flush()
        await sync_schema_relations(session, "object", obj.id, obj.metadata_)
        await session.flush()

        cms = _lido_mapping_set(
            events=[
                {
                    "id": "production",
                    "type": "Herstellung",
                    "type_concept_uri": "http://terminology.lido-schema.org/lido00007",
                },
                {
                    "id": "creation",
                    "type": "Geistige Schöpfung",
                    "type_concept_uri": "http://terminology.lido-schema.org/lido00012",
                },
            ],
            actor_rules=[
                MappingSpec(
                    source_kind=SourceKind.RELATION,
                    source_config={"relation_type": rel_type},
                    target_key="lido:events/production/actor",
                    settings={"role": "Verlag, Herausgeber"},
                    sort_order=30,
                )
            ],
            actor_types={"ind": "person", "unternehmen": "corporation"},
        )

        # Gap 3: While created entities remain drafts, build_export_context_from_db drops them all.
        ctx_draft = await build_export_context_from_db(
            session, "object", obj.id, via_relation_types=set()
        )
        assert ctx_draft.relations == []
        xml_draft = ET.tostring(LidoFormat().render(ctx_draft, cms), encoding="unicode")
        assert validate_lido_xml(xml_draft) == []
        assert ET.fromstring(xml_draft).findall(".//lido:eventActor", NS) == []

        # After publishing the entities, actors appear in LIDO — but all 4 collapse into one event/role,
        # without actorIDs and without lido:actor/@lido:type.
        for ent in created_entities:
            ent.status = "public"
        await session.flush()

        ctx_pub = await build_export_context_from_db(
            session, "object", obj.id, via_relation_types=set()
        )
        xml_pub = ET.tostring(LidoFormat().render(ctx_pub, cms), encoding="unicode")
        assert validate_lido_xml(xml_pub) == []
        root = ET.fromstring(xml_pub)

        event_terms = [e.text for e in root.findall(".//lido:eventType/lido:term", NS)]
        assert event_terms == ["Herstellung"]  # Geistige Schöpfung is lost
        exported_names = [
            e.text for e in root.findall(".//lido:eventActor//lido:appellationValue", NS)
        ]
        assert set(exported_names) == {
            "Verlag des Vereins für das Deutschtum im Ausland",
            "Novitas Verlag Otto Kellner",
            "Faber",
            "Paul Hey",
        }
        exported_roles = [e.text for e in root.findall(".//lido:roleActor/lido:term", NS)]
        assert exported_roles == ["Verlag, Herausgeber"] * 4
        assert root.findall(".//lido:actorID", NS) == []
        assert all(f"{L}type" not in a.attrib for a in root.findall(".//lido:actor", NS))

        await session.rollback()


@pytest.mark.asyncio
async def test_two_pass_actor_then_object_import_preserves_normdata_uris(app: Any) -> None:
    """Pass 1 (lido:actor -> entity with repeatable url field) + Pass 2 (lido:lido -> object) keeps actorIDs."""
    from katalon.database import AsyncSessionLocal

    xml_bytes = LIDO_XML.read_bytes()
    fmt = XmlFormat()
    actor_rows = list(fmt.parse_flat(xml_bytes, record_xpath=f"{L}actor"))
    assert len(actor_rows) == 4
    object_rows = list(fmt.parse_flat(xml_bytes, record_xpath=f"{L}lido"))
    assert len(object_rows) == 1

    suffix = uuid.uuid4().hex[:8]
    url_field_name = f"normdaten_{suffix}"
    rel_field_name = f"beteiligte_{suffix}"
    rel_type = f"creator_{suffix}"

    async with AsyncSessionLocal() as session:
        ent_label_fd = await _ensure_field(
            session, target_type="entity", name="label", label_de="Name", field_type="text"
        )
        ent_url_fd = await _ensure_field(
            session,
            target_type="entity",
            name=url_field_name,
            label_de="Normdaten",
            field_type="url",
            is_repeatable=True,
        )
        obj_title_fd = await _ensure_field(
            session, target_type="object", name="title", label_de="Titel", field_type="text"
        )
        obj_rel_fd = await _ensure_field(
            session,
            target_type="object",
            name=rel_field_name,
            label_de="Beteiligte",
            field_type="relation",
            is_repeatable=True,
            settings={"target_type": "entity", "fixed_relation_type": rel_type},
        )

        # Pass 1: import lido:actor elements as published entities (preserving GND + Wikidata actorIDs).
        ent_records, _ = apply_mapping(
            actor_rows,
            {SEL_SUB_ACTOR_NAME: "label", SEL_SUB_ACTOR_ID: url_field_name},
            {"label": ent_label_fd, url_field_name: ent_url_fd},
        )
        for idx, meta in enumerate(ent_records):
            session.add(Entity(idno=f"ENT-{suffix}-{idx}", metadata_=meta, status="public"))
        await session.flush()

        # Pass 2: import lido:lido object and resolve actors by label against the imported entities.
        obj_field_defs = {"title": obj_title_fd, rel_field_name: obj_rel_fd}
        obj_records, idnos = apply_mapping(
            object_rows,
            {SEL_IDNO: "__idno__", SEL_TITLE: "title", SEL_ACTOR_NAME: rel_field_name},
            obj_field_defs,
        )
        report = await resolve_relations(
            session,
            obj_field_defs,
            obj_records,
            {rel_field_name: {"lookup": "label", "on_missing": "create"}},
        )
        assert report.row_errors == {}
        assert report.created_records == []  # All 4 actors matched existing published entities

        obj = Object(idno=f"{idnos[0]}_{suffix}", metadata_=obj_records[0], status="public")
        session.add(obj)
        await session.flush()
        await sync_schema_relations(session, "object", obj.id, obj.metadata_)
        await session.flush()

        cms = _lido_mapping_set(
            events=[
                {
                    "id": "production",
                    "type": "Herstellung",
                    "type_concept_uri": "http://terminology.lido-schema.org/lido00007",
                }
            ],
            actor_rules=[
                MappingSpec(
                    source_kind=SourceKind.RELATION,
                    source_config={"relation_type": rel_type},
                    target_key="lido:events/production/actor",
                    settings={"role": "Verlag, Herausgeber"},
                    sort_order=30,
                )
            ],
            actor_id_fields=[{"field": url_field_name}],
        )
        ctx = await build_export_context_from_db(
            session, "object", obj.id, via_relation_types=set()
        )
        xml_out = ET.tostring(LidoFormat().render(ctx, cms), encoding="unicode")
        assert validate_lido_xml(xml_out) == []

        root = ET.fromstring(xml_out)
        paul_actor = next(
            actor
            for actor in root.findall(".//lido:eventActor//lido:actor", NS)
            if actor.findtext("lido:nameActorSet/lido:appellationValue", namespaces=NS) == "Paul Hey"
        )
        actor_ids = {
            el.attrib.get(f"{L}source"): el.text for el in paul_actor.findall("lido:actorID", NS)
        }
        assert actor_ids == {
            "GND": "https://d-nb.info/gnd/116785861",
            "Wikidata": "http://www.wikidata.org/entity/Q2060171",
        }

        await session.rollback()


@pytest.mark.asyncio
async def test_single_event_actor_only_roundtrip_emits_event_without_place(app: Any) -> None:
    """For a single actor-only event with one role and uniform subtype, two-pass round-trips completely."""
    from katalon.database import AsyncSessionLocal

    xml_bytes = _single_actor_only_event_xml()
    fmt = XmlFormat()
    actor_rows = list(fmt.parse_flat(xml_bytes, record_xpath=f"{L}actor"))
    object_rows = list(fmt.parse_flat(xml_bytes, record_xpath=f"{L}lido"))
    assert len(actor_rows) == 1
    assert actor_rows[0][SEL_SUB_ACTOR_TYPE] == "http://terminology.lido-schema.org/lido00163"

    suffix = uuid.uuid4().hex[:8]
    url_field_name = f"normdaten_{suffix}"
    rel_field_name = f"maler_{suffix}"
    rel_type = f"maler_{suffix}"

    async with AsyncSessionLocal() as session:
        ent_label_fd = await _ensure_field(
            session, target_type="entity", name="label", label_de="Name", field_type="text"
        )
        ent_url_fd = await _ensure_field(
            session,
            target_type="entity",
            name=url_field_name,
            label_de="Normdaten",
            field_type="url",
            is_repeatable=True,
        )
        obj_title_fd = await _ensure_field(
            session, target_type="object", name="title", label_de="Titel", field_type="text"
        )
        obj_rel_fd = await _ensure_field(
            session,
            target_type="object",
            name=rel_field_name,
            label_de="Maler",
            field_type="relation",
            is_repeatable=True,
            settings={"target_type": "entity", "fixed_relation_type": rel_type},
        )

        ent_records, _ = apply_mapping(
            actor_rows,
            {SEL_SUB_ACTOR_NAME: "label", SEL_SUB_ACTOR_ID: url_field_name},
            {"label": ent_label_fd, url_field_name: ent_url_fd},
        )
        session.add(
            Entity(
                idno=f"ENT-PAUL-{suffix}",
                entity_type="ind",
                metadata_=ent_records[0],
                status="public",
            )
        )
        await session.flush()

        obj_field_defs = {"title": obj_title_fd, rel_field_name: obj_rel_fd}
        obj_records, idnos = apply_mapping(
            object_rows,
            {SEL_IDNO: "__idno__", SEL_TITLE: "title", SEL_ACTOR_NAME: rel_field_name},
            obj_field_defs,
        )
        report = await resolve_relations(
            session,
            obj_field_defs,
            obj_records,
            {rel_field_name: {"lookup": "label", "on_missing": "create"}},
        )
        assert report.row_errors == {}
        assert report.created_records == []

        obj = Object(idno=f"{idnos[0]}_{suffix}", metadata_=obj_records[0], status="public")
        session.add(obj)
        await session.flush()
        await sync_schema_relations(session, "object", obj.id, obj.metadata_)
        await session.flush()

        cms = _lido_mapping_set(
            events=[
                {
                    "id": "creation",
                    "type": "Geistige Schöpfung",
                    "type_concept_uri": "http://terminology.lido-schema.org/lido00012",
                }
            ],
            actor_rules=[
                MappingSpec(
                    source_kind=SourceKind.RELATION,
                    source_config={"relation_type": rel_type},
                    target_key="lido:events/creation/actor",
                    settings={"role": "Maler / Zeichner / Illustrator"},
                    sort_order=30,
                )
            ],
            actor_id_fields=[{"field": url_field_name}],
            actor_types={"ind": "person", "unternehmen": "corporation"},
        )
        ctx = await build_export_context_from_db(
            session, "object", obj.id, via_relation_types=set()
        )
        xml_out = ET.tostring(LidoFormat().render(ctx, cms), encoding="unicode")
        assert validate_lido_xml(xml_out) == []

        root = ET.fromstring(xml_out)
        events = root.findall(".//lido:eventWrap/lido:eventSet/lido:event", NS)
        assert len(events) == 1
        event = events[0]
        assert event.findtext("lido:eventType/lido:term", namespaces=NS) == "Geistige Schöpfung"
        assert (
            event.findtext("lido:eventType/lido:conceptID", namespaces=NS)
            == "http://terminology.lido-schema.org/lido00012"
        )
        assert event.find("lido:eventPlace", NS) is None
        actor = event.find("lido:eventActor/lido:actorInRole/lido:actor", NS)
        assert actor is not None
        assert actor.attrib[f"{L}type"] == "http://terminology.lido-schema.org/lido00163"
        assert (
            actor.findtext("lido:nameActorSet/lido:appellationValue", namespaces=NS) == "Paul Hey"
        )
        actor_ids = {
            el.attrib.get(f"{L}source"): el.text for el in actor.findall("lido:actorID", NS)
        }
        assert actor_ids == {
            "GND": "https://d-nb.info/gnd/116785861",
            "Wikidata": "http://www.wikidata.org/entity/Q2060171",
        }
        assert (
            event.findtext("lido:eventActor/lido:actorInRole/lido:roleActor/lido:term", namespaces=NS)
            == "Maler / Zeichner / Illustrator"
        )

        await session.rollback()


@pytest.mark.asyncio
async def test_relation_field_without_fixed_type_rejects_lido_actor_import(app: Any) -> None:
    """A generic actor relation field without fixed_relation_type cannot resolve plain XML names."""
    from katalon.database import AsyncSessionLocal

    rows = list(XmlFormat().parse_flat(LIDO_XML.read_bytes(), record_xpath=f"{L}lido"))
    suffix = uuid.uuid4().hex[:8]
    rel_field_name = f"beteiligte_frei_{suffix}"

    async with AsyncSessionLocal() as session:
        rel_fd = FieldDefinition(
            target_type="object",
            name=rel_field_name,
            label={"de": "Beteiligte"},
            field_type="relation",
            is_repeatable=True,
            is_public=True,
            settings={"target_type": "entity"},
        )
        session.add(rel_fd)
        await session.flush()

        records, _ = apply_mapping(rows, {SEL_ACTOR_NAME: rel_field_name}, {rel_field_name: rel_fd})
        report = await resolve_relations(
            session,
            {rel_field_name: rel_fd},
            records,
            {rel_field_name: {"lookup": "label", "on_missing": "create"}},
        )
        assert 0 in report.row_errors
        assert "kein fester Relationstyp konfiguriert" in report.row_errors[0][0]
        assert rel_field_name not in records[0]

        await session.rollback()
