# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Contract tests for Katalon RDF / JSON-LD export invariants (Issue #359).

These tests verify semantic guarantees of the default RDF/JSON-LD export
skeleton using rdflib without the heavy overhead of pyshacl.

Contract commitments:
1. Syntactic well-formedness: Documents parse cleanly into rdflib Graph / Dataset.
2. Canonical URI resolution: Deterministic @id paths matching plural route patterns.
3. Skeleton primary typing: Correct CIDOC-CRM / LRMoo classes mapped per primary/subtype.
4. Fragment tolerance: Minimal records without titles/idno/relations never crash or produce invalid triples.
5. Identifier structure: crm:P1_is_identified_by maps titles to crm:E35_Title and idno to crm:E42_Identifier.
6. Controlled vocabulary integrity: skos:Concept nodes with prefLabel and exactMatch URIs.
7. Relation integrity & inverse symmetry: Standard property mappings and valid predicate URIs.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
import rdflib
from rdflib.namespace import RDF, RDFS, SKOS

from katalon.integrations.jsonld_format import (
    CRM_NS,
    DCTERMS_NS,
    LRMOO_NS,
    build_jsonld_doc,
    map_relation_property,
)

CRM = rdflib.Namespace(CRM_NS)
LRMOO = rdflib.Namespace(LRMOO_NS)
DCTERMS = rdflib.Namespace(DCTERMS_NS)


def _to_graph(doc: dict[str, Any]) -> rdflib.Graph:
    """Parse JSON-LD dictionary into an rdflib Graph to verify syntactic validity."""
    g = rdflib.Graph()
    g.parse(data=json.dumps(doc), format="json-ld")
    return g


# ---------------------------------------------------------------------------
# 1. Syntactic well-formedness & serialization roundtrip
# ---------------------------------------------------------------------------


def test_contract_serialization_roundtrip() -> None:
    """Every generated JSON-LD document must serialize cleanly to Turtle and N-Triples."""
    rec_id = str(uuid.uuid4())
    doc = build_jsonld_doc(
        record_type="object",
        record_id=rec_id,
        title="Schiffskompass",
        idno="OBJ-42",
        base_url="https://glam.example.org",
    )
    g = _to_graph(doc)

    assert len(g) > 0

    # Ensure clean serialization to standard RDF formats without errors
    turtle = g.serialize(format="turtle")
    assert "OBJ-42" in turtle

    ntriples = g.serialize(format="nt")
    assert "https://glam.example.org/objects/" in ntriples


# ---------------------------------------------------------------------------
# 2. Canonical URI resolution (@id)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("record_type", "expected_path_segment"),
    [
        ("object", "objects"),
        ("entity", "entities"),
        ("place", "places"),
        ("occurrence", "occurrences"),
        ("procedure", "procedures"),
        ("collection", "collections"),
        ("storage_location", "storage-locations"),
    ],
)
def test_contract_canonical_uri_resolution(record_type: str, expected_path_segment: str) -> None:
    """Record URIs follow canonical base URL and plural REST resource path segments."""
    rec_id = str(uuid.uuid4())

    # Case A: With configured base_url
    doc_with_base = build_jsonld_doc(
        record_type=record_type,
        record_id=rec_id,
        base_url="https://archive.org/katalon/",
    )
    expected_uri = f"https://archive.org/katalon/{expected_path_segment}/{rec_id}"
    assert doc_with_base["@id"] == expected_uri

    g = _to_graph(doc_with_base)
    subject = rdflib.URIRef(expected_uri)
    assert (subject, RDF.type, None) in g

    # Case B: Without base_url -> URN fallback
    doc_no_base = build_jsonld_doc(
        record_type=record_type,
        record_id=rec_id,
        base_url="",
    )
    expected_urn = f"urn:katalon:{record_type}:{rec_id}"
    assert doc_no_base["@id"] == expected_urn
    g_urn = _to_graph(doc_no_base)
    assert (rdflib.URIRef(expected_urn), RDF.type, None) in g_urn


# ---------------------------------------------------------------------------
# 3. Skeleton primary typing (rdf:type)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("record_type", "subtype", "expected_types"),
    [
        ("object", None, [CRM["E22_Human-Made_Object"], LRMOO["F5_Item"]]),
        ("object", "gemälde", [CRM["E22_Human-Made_Object"], LRMOO["F5_Item"]]),
        ("occurrence", "work", [LRMOO["F1_Work"]]),
        ("occurrence", "werk", [LRMOO["F1_Work"]]),
        ("occurrence", "expression", [LRMOO["F2_Expression"]]),
        ("occurrence", "fassung", [LRMOO["F2_Expression"]]),
        ("occurrence", "manifestation", [LRMOO["F3_Manifestation"]]),
        ("occurrence", "event", [CRM["E5_Event"]]),
        ("occurrence", "unbekannt", [CRM["E5_Event"]]),  # Fallback
        ("entity", "person", [CRM["E21_Person"]]),
        ("entity", "individual", [CRM["E21_Person"]]),
        ("entity", "group", [CRM["E74_Group"]]),
        ("entity", "organisation", [CRM["E74_Group"]]),
        ("entity", None, [CRM["E21_Person"]]),  # Default fallback
        ("place", None, [CRM["E53_Place"]]),
        ("procedure", None, [CRM["E7_Activity"]]),
        ("collection", None, [CRM["E78_Curated_Holding"]]),
        ("storage_location", None, [CRM["E53_Place"]]),
    ],
)
def test_contract_primary_type_mapping(
    record_type: str,
    subtype: str | None,
    expected_types: list[rdflib.URIRef],
) -> None:
    """Every record must map to its specified CIDOC-CRM / LRMoo classes."""
    rec_id = str(uuid.uuid4())
    doc = build_jsonld_doc(
        record_type=record_type,
        record_id=rec_id,
        subtype=subtype,
        base_url="https://glam.test",
    )
    g = _to_graph(doc)
    subject = rdflib.URIRef(doc["@id"])

    actual_types = set(g.objects(subject=subject, predicate=RDF.type))
    for expected_type in expected_types:
        assert expected_type in actual_types, (
            f"Expected {expected_type} for {record_type}/{subtype}, got {actual_types}"
        )


# ---------------------------------------------------------------------------
# 4. Fragment tolerance (legitimately incomplete museum records)
# ---------------------------------------------------------------------------


def test_contract_fragment_tolerance_minimal_record() -> None:
    """Minimal records without title, idno, metadata or relations must remain valid RDF."""
    rec_id = str(uuid.uuid4())
    doc = build_jsonld_doc(
        record_type="occurrence",
        record_id=rec_id,
        title=None,
        idno=None,
        subtype=None,
        metadata={},
        relations=[],
        base_url="https://glam.test",
    )
    g = _to_graph(doc)
    subject = rdflib.URIRef(doc["@id"])

    # Must have a type
    assert (subject, RDF.type, None) in g
    # Fallback label must be record_id
    labels = list(g.objects(subject=subject, predicate=RDFS.label))
    assert len(labels) == 1
    assert str(labels[0]) == rec_id

    # Must NOT have empty string literals or broken identifiers
    for _, _, obj in g:
        if isinstance(obj, rdflib.Literal):
            assert str(obj).strip() != "", "Empty string literals are prohibited in RDF export"


# ---------------------------------------------------------------------------
# 5. Identifier & title structure (crm:P1_is_identified_by)
# ---------------------------------------------------------------------------


def test_contract_identifiers_structure() -> None:
    """Titles and inventory numbers must be typed as E35_Title and E42_Identifier."""
    rec_id = str(uuid.uuid4())
    doc = build_jsonld_doc(
        record_type="object",
        record_id=rec_id,
        title="Flugblatt 1848",
        idno="INV-1848-01",
        base_url="https://glam.test",
    )
    g = _to_graph(doc)
    subject = rdflib.URIRef(doc["@id"])

    # Direct properties
    assert (subject, CRM["P102_has_title"], rdflib.Literal("Flugblatt 1848")) in g

    # P1_is_identified_by nodes
    identifier_nodes = list(g.objects(subject=subject, predicate=CRM["P1_is_identified_by"]))
    assert len(identifier_nodes) == 2

    # Verify E35_Title node
    title_nodes = [node for node in identifier_nodes if (node, RDF.type, CRM["E35_Title"]) in g]
    assert len(title_nodes) == 1
    assert (title_nodes[0], RDFS.label, rdflib.Literal("Flugblatt 1848")) in g

    # Verify E42_Identifier node
    idno_nodes = [node for node in identifier_nodes if (node, RDF.type, CRM["E42_Identifier"]) in g]
    assert len(idno_nodes) == 1
    assert (idno_nodes[0], CRM["P190_has_symbolic_content"], rdflib.Literal("INV-1848-01")) in g


# ---------------------------------------------------------------------------
# 6. Controlled vocabulary integrity (skos:Concept)
# ---------------------------------------------------------------------------


def test_contract_vocabulary_concept_subgraph() -> None:
    """Concepts must serialize with skos:Concept type, prefLabel and external exactMatch URIs."""
    rec_id = str(uuid.uuid4())
    vocab_concepts = {
        "pergament": {
            "@type": "skos:Concept",
            "@id": "http://vocab.getty.edu/aat/300014284",
            "skos:prefLabel": {"@value": "Pergament", "@language": "de"},
            "skos:exactMatch": ["https://d-nb.info/gnd/4173740-4"],
        }
    }

    doc = build_jsonld_doc(
        record_type="object",
        record_id=rec_id,
        metadata={"beschreibstoff": "pergament"},
        vocab_concepts=vocab_concepts,
        base_url="https://glam.test",
    )
    g = _to_graph(doc)
    subject = rdflib.URIRef(doc["@id"])

    concept_uri = rdflib.URIRef("http://vocab.getty.edu/aat/300014284")
    assert (subject, CRM["P2_has_type"], concept_uri) in g
    assert (concept_uri, RDF.type, SKOS.Concept) in g
    assert (concept_uri, SKOS.prefLabel, rdflib.Literal("Pergament", lang="de")) in g
    assert (concept_uri, SKOS.exactMatch, rdflib.URIRef("https://d-nb.info/gnd/4173740-4")) in g


# ---------------------------------------------------------------------------
# 7. Relation mapping and inverse symmetry
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("relation_name", "expected_prop", "expected_inverse"),
    [
        ("is_realised_in", "lrmoo:R3_is_realised_in", "lrmoo:R3i_realises"),
        ("is_embodied_in", "lrmoo:R4_is_embodied_in", "lrmoo:R4i_embodies"),
        ("exemplifies", "lrmoo:R7_exemplifies", "lrmoo:R7i_is_exemplified_by"),
        ("carried_out_by", "crm:P14_carried_out_by", "crm:P14i_performed"),
        ("represents", "crm:P138_represents", "crm:P138i_is_represented_by"),
        ("took_place_at", "crm:P7_took_place_at", "crm:P7i_witnessed"),
        ("refers_to", "crm:P67_refers_to", "crm:P67i_is_referred_to_by"),
        ("is_composed_of", "crm:P46_is_composed_of", "crm:P46i_forms_part_of"),
        ("has_current_owner", "crm:P52_has_current_owner", "crm:P52i_is_current_owner_of"),
    ],
)
def test_contract_relation_mapping_and_inverse_symmetry(
    relation_name: str,
    expected_prop: str,
    expected_inverse: str,
) -> None:
    """Forward and inverse property mappings must be defined and symmetrically mapped."""
    forward = map_relation_property(relation_name, is_inverse=False)
    assert forward == expected_prop

    inverse = map_relation_property(relation_name, is_inverse=True)
    assert inverse == expected_inverse


def test_contract_relations_in_graph() -> None:
    """Relations between records must link canonical URIs with target typing and labels."""
    source_id = str(uuid.uuid4())
    target_id = str(uuid.uuid4())

    relations = [
        {
            "target_type": "entity",
            "target_id": target_id,
            "target_subtype": "person",
            "label": "Clara Schumann",
            "relation_type": "komponiert_von",
        }
    ]

    doc = build_jsonld_doc(
        record_type="occurrence",
        record_id=source_id,
        subtype="work",
        title="Klavierkonzert a-Moll op. 7",
        relations=relations,
        base_url="https://glam.test",
    )
    g = _to_graph(doc)
    source_uri = rdflib.URIRef(doc["@id"])
    target_uri = rdflib.URIRef(f"https://glam.test/entities/{target_id}")

    # P14 carried out by relation
    assert (source_uri, CRM["P14_carried_out_by"], target_uri) in g
    # Target entity typing and label
    assert (target_uri, RDF.type, CRM["E21_Person"]) in g
    assert (target_uri, RDFS.label, rdflib.Literal("Clara Schumann")) in g
