# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import json
import xml.etree.ElementTree as ET

import rdflib

from katalon.integrations.jsonld_format import (
    JsonLdFormat,
    build_jsonld_doc,
    map_primary_type,
    map_relation_property,
)


def test_map_primary_type_occurrence() -> None:
    assert map_primary_type("occurrence", "work") == "lrmoo:F1_Work"
    assert map_primary_type("occurrence", "werk") == "lrmoo:F1_Work"
    assert map_primary_type("occurrence", "expression") == "lrmoo:F2_Expression"
    assert map_primary_type("occurrence", "ausgabe") == "lrmoo:F2_Expression"
    assert map_primary_type("occurrence", "manifestation") == "lrmoo:F3_Manifestation"
    assert map_primary_type("occurrence", "event") == "crm:E5_Event"
    assert map_primary_type("occurrence", "ausstellung") == "crm:E5_Event"
    assert map_primary_type("occurrence", "other") == "crm:E5_Event"


def test_map_primary_type_object() -> None:
    types = map_primary_type("object")
    assert isinstance(types, list)
    assert "crm:E22_Human-Made_Object" in types
    assert "lrmoo:F5_Item" in types


def test_map_primary_type_entity() -> None:
    assert map_primary_type("entity", "person") == "crm:E21_Person"
    assert map_primary_type("entity") == "crm:E21_Person"
    assert map_primary_type("entity", "organization") == "crm:E74_Group"
    assert map_primary_type("entity", "group") == "crm:E74_Group"
    assert map_primary_type("entity", "institution") == "crm:E74_Group"


def test_map_primary_type_place() -> None:
    assert map_primary_type("place") == "crm:E53_Place"


def test_map_relation_properties() -> None:
    assert map_relation_property("is_realised_in") == "lrmoo:R3_is_realised_in"
    assert map_relation_property("R3_is_realised_in") == "lrmoo:R3_is_realised_in"
    assert map_relation_property("is_embodied_in") == "lrmoo:R4_is_embodied_in"
    assert map_relation_property("R4_is_embodied_in") == "lrmoo:R4_is_embodied_in"
    assert map_relation_property("exemplifies") == "lrmoo:R7_exemplifies"
    assert map_relation_property("R7_exemplifies") == "lrmoo:R7_exemplifies"
    assert map_relation_property("carried_out_by") == "crm:P14_carried_out_by"
    assert map_relation_property("fotografiert_von") == "crm:P14_carried_out_by"
    assert map_relation_property("verfasst_von") == "crm:P14_carried_out_by"
    assert map_relation_property("zeigt") == "crm:P138_represents"
    assert map_relation_property("spielt_in") == "crm:P7_took_place_at"
    assert map_relation_property("bezieht_sich_auf") == "crm:P67_refers_to"


def test_map_relation_inverse_properties() -> None:
    assert map_relation_property("is_realised_in", is_inverse=True) == "lrmoo:R3i_realises"
    assert map_relation_property("is_embodied_in", is_inverse=True) == "lrmoo:R4i_embodies"
    assert map_relation_property("exemplifies", is_inverse=True) == "lrmoo:R7i_is_exemplified_by"
    assert map_relation_property("carried_out_by", is_inverse=True) == "crm:P14i_performed"


def test_build_jsonld_doc_with_vocab_concepts_and_relations() -> None:
    vocab_concepts = {
        "holz": {
            "@type": "skos:Concept",
            "@id": "http://vocab.getty.edu/aat/300011914",
            "skos:prefLabel": {"@value": "Holz", "@language": "de"},
            "skos:exactMatch": ["https://d-nb.info/gnd/4025668-6"],
        }
    }

    relations = [
        {
            "target_type": "occurrence",
            "target_id": "occ-123",
            "target_subtype": "manifestation",
            "label": "Erstausgabe 1890",
            "relation_type": "exemplifies",
        },
        {
            "target_type": "entity",
            "target_id": "ent-456",
            "target_subtype": "person",
            "label": "August Sander",
            "relation_type": "fotografiert_von",
        },
    ]

    doc = build_jsonld_doc(
        record_type="object",
        record_id="obj-789",
        title="Blick auf Marrakesch",
        idno="KAT-2026-001",
        subtype="foto",
        metadata={"material": "holz", "beschreibung": "Eine historische Fotografie."},
        relations=relations,
        vocab_concepts=vocab_concepts,
        base_url="https://katalon.example.org",
    )

    assert doc["@id"] == "https://katalon.example.org/objects/obj-789"
    assert "crm:E22_Human-Made_Object" in doc["@type"]
    assert "lrmoo:F5_Item" in doc["@type"]
    assert doc["rdfs:label"] == "Blick auf Marrakesch"
    assert doc["crm:P102_has_title"] == "Blick auf Marrakesch"
    assert doc["crm:P3_has_note"] == "Eine historische Fotografie."

    # Vocabulary Concept in crm:P2_has_type
    p2_types = doc["crm:P2_has_type"]
    if isinstance(p2_types, dict):
        p2_types = [p2_types]
    concept_nodes = [t for t in p2_types if t.get("@type") == "skos:Concept"]
    assert len(concept_nodes) == 1
    assert concept_nodes[0]["@id"] == "http://vocab.getty.edu/aat/300011914"
    assert concept_nodes[0]["skos:exactMatch"] == ["https://d-nb.info/gnd/4025668-6"]

    # Relations resolved
    assert "lrmoo:R7_exemplifies" in doc
    assert doc["lrmoo:R7_exemplifies"]["@id"] == "https://katalon.example.org/occurrences/occ-123"
    assert doc["lrmoo:R7_exemplifies"]["@type"] == "lrmoo:F3_Manifestation"
    assert doc["lrmoo:R7_exemplifies"]["rdfs:label"] == "Erstausgabe 1890"

    assert "crm:P14_carried_out_by" in doc
    assert doc["crm:P14_carried_out_by"]["@id"] == "https://katalon.example.org/entities/ent-456"
    assert doc["crm:P14_carried_out_by"]["@type"] == "crm:E21_Person"
    assert doc["crm:P14_carried_out_by"]["rdfs:label"] == "August Sander"

    # Verify RDFLib parsing and serialization to Turtle
    g = rdflib.Graph()
    g.parse(data=json.dumps(doc), format="json-ld")
    turtle = g.serialize(format="turtle")
    assert "lrmoo:F5_Item" in turtle or "http://iflastandards.info/ns/lrm/lrmoo/F5_Item" in turtle
    assert "R7_exemplifies" in turtle or "http://iflastandards.info/ns/lrm/lrmoo/R7_exemplifies" in turtle
    assert "P14_carried_out_by" in turtle or "http://www.cidoc-crm.org/cidoc-crm/P14_carried_out_by" in turtle


def test_jsonld_format_render_for_oaipmh() -> None:
    fmt = JsonLdFormat()
    assert fmt.key == "json_ld"
    assert fmt.namespace == "http://www.w3.org/ns/json-ld"

    hit = {
        "_id": "550e8400-e29b-41d4-a716-446655440000",
        "_source": {
            "record_type": "occurrence",
            "subtype": "work",
            "title": "Faust. Eine Tragödie.",
            "idno": "WERK-001",
            "metadata": {
                "beschreibung": "Goethes Hauptwerk.",
            },
            "adv_relations": [
                {
                    "target_type": "occurrence",
                    "target_id": "expr-999",
                    "relation_type": "is_realised_in",
                }
            ],
        },
    }

    el = fmt.render(hit, {})
    assert el.tag == "json_ld"
    assert el.attrib["xmlns"] == "http://www.w3.org/ns/json-ld"
    assert el.text is not None

    parsed_doc = json.loads(el.text)
    assert parsed_doc["@type"] == "lrmoo:F1_Work"
    assert parsed_doc["rdfs:label"] == "Faust. Eine Tragödie."
    assert "lrmoo:R3_is_realised_in" in parsed_doc
    assert parsed_doc["lrmoo:R3_is_realised_in"]["@id"] == "urn:katalon:occurrence:expr-999"

    # Test round-trip in XML ElementTree
    xml_str = ET.tostring(el, encoding="unicode")
    root = ET.fromstring(xml_str)
    unpacked_json = json.loads(root.text or "")
    assert unpacked_json["@type"] == "lrmoo:F1_Work"


def test_relation_deduplication_by_id() -> None:
    relations = [
        {"target_type": "place", "target_id": "plc-1", "label": "Weimar", "relation_type": "zeigt"},
        {"target_type": "place", "target_id": "plc-1", "label": "Weimar", "relation_type": "zeigt"},
    ]
    doc = build_jsonld_doc(
        record_type="object",
        record_id="obj-1",
        relations=relations,
    )
    represents = doc["crm:P138_represents"]
    assert isinstance(represents, dict)
    assert represents["@id"] == "urn:katalon:place:plc-1"
