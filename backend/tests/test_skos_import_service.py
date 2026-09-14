# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from katalon.services.skos_import_service import (
    detect_rdf_format,
    parse_skos_terms,
)

SAMPLE_TURTLE = """
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix ex: <http://example.org/vocab/> .

ex:art_materials a skos:ConceptScheme ;
    rdfs:label "Art Materials Scheme"@en ;
    skos:hasTopConcept ex:paint .

ex:paint a skos:Concept ;
    skos:notation "P-01" ;
    skos:prefLabel "Farbe"@de, "Paint"@en ;
    skos:altLabel "Anstrichstoff"@de, "Colouring matter"@en ;
    skos:topConceptOf ex:art_materials ;
    skos:inScheme ex:art_materials ;
    skos:narrower ex:oil_paint ;
    skos:exactMatch <http://vocab.getty.edu/aat/300015050> .

ex:oil_paint a skos:Concept ;
    skos:notation "P-02" ;
    skos:prefLabel "Ölfarbe"@de, "Oil paint"@en ;
    skos:altLabel "Ölmalfarbe"@de ;
    skos:broader ex:paint ;
    skos:inScheme ex:art_materials ;
    skos:narrower ex:linseed_oil_paint ;
    skos:exactMatch <http://vocab.getty.edu/aat/300026816> .

ex:linseed_oil_paint a skos:Concept ;
    skos:prefLabel "Leinölfarbe"@de, "Linseed oil paint"@en ;
    skos:broader ex:oil_paint ;
    skos:inScheme ex:art_materials .

ex:sculpture a skos:Concept ;
    skos:prefLabel "Skulptur"@de, "Sculpture"@en ;
    skos:exactMatch <http://vocab.getty.edu/aat/300047090> .
""".encode()

SAMPLE_RDF_XML = b"""<?xml version="1.0" encoding="utf-8"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:skos="http://www.w3.org/2004/02/skos/core#">
  <skos:ConceptScheme rdf:about="http://example.org/scheme/photo">
    <skos:prefLabel xml:lang="de">Fotografische Verfahren</skos:prefLabel>
  </skos:ConceptScheme>

  <skos:Concept rdf:about="http://example.org/concept/daguerreotype">
    <skos:prefLabel xml:lang="de">Daguerreotypie</skos:prefLabel>
    <skos:prefLabel xml:lang="en">Daguerreotype</skos:prefLabel>
    <skos:inScheme rdf:resource="http://example.org/scheme/photo"/>
    <skos:exactMatch rdf:resource="http://vocab.getty.edu/aat/300022568"/>
  </skos:Concept>
</rdf:RDF>
"""

SAMPLE_JSON_LD = b"""{
  "@context": {
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "prefLabel": {"@id": "skos:prefLabel"},
    "broader": {"@id": "skos:broader", "@type": "@id"},
    "Concept": "skos:Concept"
  },
  "@graph": [
    {
      "@id": "http://example.org/c/book",
      "@type": "Concept",
      "prefLabel": [{"@value": "Buch", "@language": "de"}, {"@value": "Book", "@language": "en"}]
    },
    {
      "@id": "http://example.org/c/monograph",
      "@type": "Concept",
      "prefLabel": [{"@value": "Monografie", "@language": "de"}],
      "broader": "http://example.org/c/book"
    }
  ]
}
"""


def test_detect_rdf_format() -> None:
    assert detect_rdf_format("thesaurus.ttl") == "turtle"
    assert detect_rdf_format("vocab.rdf") == "xml"
    assert detect_rdf_format("vocab.xml") == "xml"
    assert detect_rdf_format("export.jsonld") == "json-ld"
    assert detect_rdf_format("export.json", content=SAMPLE_JSON_LD) == "json-ld"
    assert detect_rdf_format("export.nt") == "nt"


def test_parse_skos_turtle_full() -> None:
    terms, errors, meta = parse_skos_terms(SAMPLE_TURTLE, filename="test.ttl")

    assert errors == []
    assert len(terms) == 4
    assert meta["total_concepts_found"] == 4
    assert meta["total_concepts_selected"] == 4
    assert len(meta["detected_schemes"]) == 1
    assert meta["detected_schemes"][0]["uri"] == "http://example.org/vocab/art_materials"

    terms_by_uri = {t.uri: t for t in terms}

    paint = terms_by_uri["http://example.org/vocab/paint"]
    assert paint.label == {"de": "Farbe", "en": "Paint"}
    assert paint.term == "p-01"
    assert paint.parent_term is None
    assert paint.exact_match_uris == ["http://vocab.getty.edu/aat/300015050"]
    assert paint.metadata["alt_labels"]["de"] == ["Anstrichstoff"]
    assert paint.metadata["alt_labels"]["en"] == ["Colouring matter"]

    oil_paint = terms_by_uri["http://example.org/vocab/oil_paint"]
    assert oil_paint.label == {"de": "Ölfarbe", "en": "Oil paint"}
    assert oil_paint.term == "p-02"
    assert oil_paint.parent_term == "p-01"
    assert oil_paint.exact_match_uris == ["http://vocab.getty.edu/aat/300026816"]
    assert oil_paint.metadata["alt_labels"]["de"] == ["Ölmalfarbe"]

    linseed = terms_by_uri["http://example.org/vocab/linseed_oil_paint"]
    assert linseed.parent_term == "p-02"


def test_parse_skos_non_hierarchical() -> None:
    terms, errors, _ = parse_skos_terms(
        SAMPLE_TURTLE, filename="test.ttl", is_hierarchical=False
    )
    assert errors == []
    # All parent_terms should be None
    for term in terms:
        assert term.parent_term is None


def test_parse_skos_rdf_xml() -> None:
    terms, errors, meta = parse_skos_terms(SAMPLE_RDF_XML, filename="photo.rdf")
    assert errors == []
    assert len(terms) == 1
    assert terms[0].uri == "http://example.org/concept/daguerreotype"
    assert terms[0].label == {"de": "Daguerreotypie", "en": "Daguerreotype"}
    assert terms[0].exact_match_uris == ["http://vocab.getty.edu/aat/300022568"]
    assert len(meta["detected_schemes"]) == 1


def test_parse_skos_json_ld() -> None:
    terms, errors, _ = parse_skos_terms(SAMPLE_JSON_LD, filename="vocab.jsonld")
    assert errors == []
    assert len(terms) == 2
    terms_by_uri = {t.uri: t for t in terms}
    book = terms_by_uri["http://example.org/c/book"]
    monograph = terms_by_uri["http://example.org/c/monograph"]
    assert monograph.parent_term == book.term


def test_parse_skos_filter_by_concept_scheme() -> None:
    terms, errors, meta = parse_skos_terms(
        SAMPLE_TURTLE,
        filename="test.ttl",
        concept_scheme="http://example.org/vocab/art_materials",
    )
    assert errors == []
    assert len(terms) == 3
    uris = {t.uri for t in terms}
    assert "http://example.org/vocab/paint" in uris
    assert "http://example.org/vocab/oil_paint" in uris
    assert "http://example.org/vocab/linseed_oil_paint" in uris
    # sculpture is not in the scheme
    assert "http://example.org/vocab/sculpture" not in uris


def test_parse_skos_filter_by_top_concept() -> None:
    terms, errors, _ = parse_skos_terms(
        SAMPLE_TURTLE,
        filename="test.ttl",
        top_concept="http://example.org/vocab/oil_paint",
    )
    assert errors == []
    assert len(terms) == 2
    uris = {t.uri for t in terms}
    # Should only include oil_paint and linseed_oil_paint
    assert "http://example.org/vocab/oil_paint" in uris
    assert "http://example.org/vocab/linseed_oil_paint" in uris
    assert "http://example.org/vocab/paint" not in uris


def test_parse_skos_filter_by_top_concept_with_max_depth() -> None:
    # Depth 1 from paint: only paint
    terms_d1, _, _ = parse_skos_terms(
        SAMPLE_TURTLE,
        filename="test.ttl",
        top_concept="http://example.org/vocab/paint",
        max_depth=1,
    )
    assert len(terms_d1) == 1
    assert terms_d1[0].uri == "http://example.org/vocab/paint"

    # Depth 2 from paint: paint + oil_paint
    terms_d2, _, _ = parse_skos_terms(
        SAMPLE_TURTLE,
        filename="test.ttl",
        top_concept="http://example.org/vocab/paint",
        max_depth=2,
    )
    assert len(terms_d2) == 2
    uris = {t.uri for t in terms_d2}
    assert "http://example.org/vocab/paint" in uris
    assert "http://example.org/vocab/oil_paint" in uris


def test_parse_skos_top_concept_not_found() -> None:
    terms, errors, _ = parse_skos_terms(
        SAMPLE_TURTLE,
        filename="test.ttl",
        top_concept="http://example.org/vocab/nonexistent",
    )
    assert len(terms) == 0
    assert len(errors) == 1
    assert "nicht gefunden" in errors[0]["message"]


def test_parse_skos_max_terms_cap() -> None:
    terms, errors, meta = parse_skos_terms(
        SAMPLE_TURTLE,
        filename="test.ttl",
        max_terms=2,
    )
    assert len(terms) == 2
    assert meta["total_concepts_selected"] == 2
    assert len(errors) == 1
    assert "Mengenbegrenzung" in errors[0]["message"]
