# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import uuid

import pytest
import rdflib


@pytest.mark.asyncio
async def test_rdf_export_single_records_and_negotiation(async_client, auth_headers) -> None:
    # 1. Create a Vocabulary and a VocabularyTerm with canonical URI
    vocab_res = await async_client.post(
        "/v1/vocabularies",
        headers=auth_headers,
        json={
            "name": f"materials_{uuid.uuid4().hex[:8]}",
            "is_hierarchical": False,
            "canonical_uri": "http://vocab.getty.edu/aat/",
        },
    )
    assert vocab_res.status_code == 201, vocab_res.text
    vocab = vocab_res.json()

    term_res = await async_client.post(
        f"/v1/vocabularies/{vocab['id']}/terms",
        headers=auth_headers,
        json={
            "vocabulary_id": vocab["id"],
            "term": "gold",
            "label": {"de": "Gold", "en": "Gold"},
            "uri": "http://vocab.getty.edu/aat/300011029",
            "exact_match_uris": ["https://d-nb.info/gnd/4157819-3"],
        },
    )
    assert term_res.status_code == 201, term_res.text

    # Create subtypes for occurrence, entity, place, object
    for ptype, sname in [
        ("occurrence", "work"),
        ("occurrence", "manifestation"),
        ("entity", "person"),
        ("place", "city"),
        ("object", "partitur"),
    ]:
        sub_res = await async_client.post(
            "/v1/record-subtypes",
            headers=auth_headers,
            json={
                "primary_type": ptype,
                "name": sname,
                "label": {"de": sname.capitalize()},
            },
        )
        assert sub_res.status_code in (201, 400), sub_res.text

    # 2. Create Occurrence (Work & Manifestation)
    work_res = await async_client.post(
        "/v1/occurrences",
        headers=auth_headers,
        json={
            "idno": f"WORK-{uuid.uuid4().hex[:8]}",
            "occurrence_type": "work",
            "status": "draft",
            "metadata_": {"titel": "Die Zauberflöte"},
        },
    )
    assert work_res.status_code == 201, work_res.text
    work = work_res.json()

    manif_res = await async_client.post(
        "/v1/occurrences",
        headers=auth_headers,
        json={
            "idno": f"MANIF-{uuid.uuid4().hex[:8]}",
            "occurrence_type": "manifestation",
            "status": "draft",
            "metadata_": {"titel": "Erstausgabe Wien 1791"},
        },
    )
    assert manif_res.status_code == 201, manif_res.text
    manifestation = manif_res.json()

    # 3. Create Entity (Person)
    person_res = await async_client.post(
        "/v1/entities",
        headers=auth_headers,
        json={
            "idno": f"PERS-{uuid.uuid4().hex[:8]}",
            "entity_type": "person",
            "status": "draft",
            "metadata_": {"name": "Wolfgang Amadeus Mozart"},
        },
    )
    assert person_res.status_code == 201, person_res.text
    person = person_res.json()

    # 4. Create Place
    place_res = await async_client.post(
        "/v1/places",
        headers=auth_headers,
        json={
            "idno": f"PLACE-{uuid.uuid4().hex[:8]}",
            "place_type": "city",
            "status": "draft",
            "metadata_": {"name": "Wien"},
        },
    )
    assert place_res.status_code == 201, place_res.text
    place = place_res.json()

    # 5. Create Object (Item) with vocabulary term and relations
    obj_res = await async_client.post(
        "/v1/objects",
        headers=auth_headers,
        json={
            "idno": f"OBJ-{uuid.uuid4().hex[:8]}",
            "object_type": "partitur",
            "status": "draft",
            "metadata_": {
                "titel": "Originalpartitur Zauberflöte",
                "material": "gold",
                "beschreibung": "Handschriftliche Partitur.",
            },
        },
    )
    assert obj_res.status_code == 201, obj_res.text
    obj = obj_res.json()

    # Add relations: Object exemplifiziert Manifestation, Person carried_out_by
    rel1 = await async_client.post(
        "/v1/relations",
        headers=auth_headers,
        json={
            "from_type": "object",
            "from_id": obj["id"],
            "to_type": "occurrence",
            "to_id": manifestation["id"],
            "relation_type": "exemplifies",
        },
    )
    assert rel1.status_code == 201, rel1.text

    rel2 = await async_client.post(
        "/v1/relations",
        headers=auth_headers,
        json={
            "from_type": "object",
            "from_id": obj["id"],
            "to_type": "entity",
            "to_id": person["id"],
            "relation_type": "komponiert_von",
        },
    )
    assert rel2.status_code == 201, rel2.text

    # -------------------------------------------------------------
    # Test GET /v1/objects/{id}/export?format=jsonld
    # -------------------------------------------------------------
    exp_res = await async_client.get(
        f"/v1/objects/{obj['id']}/export?format=jsonld",
        headers=auth_headers,
    )
    assert exp_res.status_code == 200, exp_res.text
    assert "application/ld+json" in exp_res.headers["content-type"]
    doc = exp_res.json()

    # Verify Object types (CIDOC-CRM E22 and LRMoo F5)
    assert "crm:E22_Human-Made_Object" in doc["@type"]
    assert "lrmoo:F5_Item" in doc["@type"]

    # Verify vocabulary concept resolution with canonical URI
    p2_types = doc.get("crm:P2_has_type", [])
    if isinstance(p2_types, dict):
        p2_types = [p2_types]
    concept = next((c for c in p2_types if c.get("@type") == "skos:Concept"), None)
    assert concept is not None
    assert concept["@id"] == "http://vocab.getty.edu/aat/300011029"
    assert concept["skos:exactMatch"] == ["https://d-nb.info/gnd/4157819-3"]

    # Verify relations resolution:
    # lrmoo:R7_exemplifies
    assert "lrmoo:R7_exemplifies" in doc
    assert str(manifestation["id"]) in doc["lrmoo:R7_exemplifies"]["@id"]
    assert doc["lrmoo:R7_exemplifies"]["@type"] == "lrmoo:F3_Manifestation"

    # crm:P14_carried_out_by (from 'komponiert_von')
    assert "crm:P14_carried_out_by" in doc
    assert str(person["id"]) in doc["crm:P14_carried_out_by"]["@id"]
    assert doc["crm:P14_carried_out_by"]["@type"] == "crm:E21_Person"

    # -------------------------------------------------------------
    # Test Content Negotiation on GET /v1/objects/{id} with Accept: application/ld+json
    # -------------------------------------------------------------
    neg_res = await async_client.get(
        f"/v1/objects/{obj['id']}",
        headers={**auth_headers, "Accept": "application/ld+json"},
    )
    assert neg_res.status_code == 200, neg_res.text
    assert "application/ld+json" in neg_res.headers["content-type"]
    neg_doc = neg_res.json()
    assert "crm:E22_Human-Made_Object" in neg_doc["@type"]

    # -------------------------------------------------------------
    # Test Turtle format export
    # -------------------------------------------------------------
    ttl_res = await async_client.get(
        f"/v1/objects/{obj['id']}/export?format=turtle",
        headers=auth_headers,
    )
    assert ttl_res.status_code == 200, ttl_res.text
    assert "text/turtle" in ttl_res.headers["content-type"]
    assert "lrmoo:F5_Item" in ttl_res.text or "crm:E22_Human-Made_Object" in ttl_res.text

    # Parse with rdflib to verify valid RDF
    g = rdflib.Graph()
    g.parse(data=ttl_res.text, format="turtle")
    assert len(g) > 0

    # -------------------------------------------------------------
    # Test GET /v1/export/objects/{id}?format=jsonld
    # -------------------------------------------------------------
    generic_exp = await async_client.get(
        f"/v1/export/objects/{obj['id']}?format=jsonld",
        headers=auth_headers,
    )
    assert generic_exp.status_code == 200, generic_exp.text
    assert generic_exp.json()["@id"] == doc["@id"]

    # -------------------------------------------------------------
    # Test Occurrence Export (Work)
    # -------------------------------------------------------------
    work_exp = await async_client.get(
        f"/v1/occurrences/{work['id']}/export?format=jsonld",
        headers=auth_headers,
    )
    assert work_exp.status_code == 200, work_exp.text
    work_doc = work_exp.json()
    assert work_doc["@type"] == "lrmoo:F1_Work"

    # -------------------------------------------------------------
    # Test Entity Export (Person)
    # -------------------------------------------------------------
    entity_exp = await async_client.get(
        f"/v1/entities/{person['id']}/export?format=jsonld",
        headers=auth_headers,
    )
    assert entity_exp.status_code == 200, entity_exp.text
    assert entity_exp.json()["@type"] == "crm:E21_Person"

    # -------------------------------------------------------------
    # Test Place Export
    # -------------------------------------------------------------
    place_exp = await async_client.get(
        f"/v1/places/{place['id']}/export?format=jsonld",
        headers=auth_headers,
    )
    assert place_exp.status_code == 200, place_exp.text
    assert place_exp.json()["@type"] == "crm:E53_Place"


@pytest.mark.asyncio
async def test_oai_pmh_json_ld_integration(async_client, auth_headers) -> None:
    # 1. Fetch field definitions to find a public field for object
    fields_res = await async_client.get(
        "/v1/schema/object",
        headers=auth_headers,
    )
    assert fields_res.status_code == 200, fields_res.text
    fields = fields_res.json()
    assert len(fields) > 0
    field_id = fields[0]["id"]

    # 2. Create mapping for json_ld format
    mapping_res = await async_client.post(
        "/v1/metadata-mappings",
        headers=auth_headers,
        json={
            "field_definition_id": field_id,
            "format_key": "json_ld",
            "target_path": "crm:P102_has_title",
            "sort_order": 0,
            "is_enabled": True,
        },
    )
    assert mapping_res.status_code == 201, mapping_res.text

    # 3. Call OAI-PMH ListMetadataFormats
    oai_res = await async_client.get("/oai?verb=ListMetadataFormats")
    assert oai_res.status_code == 200, oai_res.text
    assert "<metadataPrefix>json_ld</metadataPrefix>" in oai_res.text
    assert "http://www.w3.org/ns/json-ld" in oai_res.text
