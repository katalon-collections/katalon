# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import xml.etree.ElementTree as ET
from types import SimpleNamespace

from katalon.config import settings
from katalon.integrations.jsonld_format import JsonLdFormat
from katalon.integrations.oai_dc_format import OaiDcFormat
from katalon.services import oaipmh_service

OAI_DC = OaiDcFormat()


def test_identify_contains_repository_name() -> None:
    xml = oaipmh_service.identify(
        "http://test/oai", "Katalon", "admin@test.com", "2000-01-01T00:00:00Z"
    )
    root = ET.fromstring(xml.split("\n", 1)[-1] if xml.startswith("<?") else xml)
    names = root.findall(".//{http://www.openarchives.org/OAI/2.0/}repositoryName")
    assert any("Katalon" in n.text for n in names if n.text)


def test_list_sets_contains_four_sets() -> None:
    sets = [
        SimpleNamespace(set_spec=spec, set_name=spec.capitalize())
        for spec in ("object", "entity", "place", "occurrence")
    ]
    xml = oaipmh_service.list_sets(sets, "http://test/oai")
    root = ET.fromstring(xml.split("\n", 1)[-1] if xml.startswith("<?") else xml)
    specs = root.findall(".//{http://www.openarchives.org/OAI/2.0/}setSpec")
    assert {s.text for s in specs} >= {"object", "entity", "place", "occurrence"}


def test_bad_verb() -> None:
    xml = oaipmh_service.bad_verb("Nonsense", "http://test/oai")
    assert "badVerb" in xml


def _mock_hit() -> dict:
    return {
        "_id": "550e8400-e29b-41d4-a716-446655440000",
        "_source": {
            "record_type": "object",
            "title": "Test Foto",
            "idno": "TEST-001",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-06-01T00:00:00Z",
            "metadata": {},
        },
    }


def test_get_record_requires_mapping_no_title_without_it() -> None:
    # Format-agnostic rendering: without an explicit mapping, no content fields are guessed.
    hit = _mock_hit()
    xml = oaipmh_service.get_record(
        hit, "http://test/oai", "oai:katalon:object:550e8400", "oai_dc", OAI_DC
    )
    assert "Test Foto" not in xml
    assert "<dc:type>object</dc:type>" in xml


def test_get_record_contains_dc_title_when_mapped() -> None:
    hit = _mock_hit()
    mapping_index = {"object": {"title": ["dc:title"]}}
    xml = oaipmh_service.get_record(
        hit, "http://test/oai", "oai:katalon:object:550e8400", "oai_dc", OAI_DC, mapping_index
    )
    assert "<dc:title>Test Foto</dc:title>" in xml


def test_get_record_uses_configured_dc_mapping() -> None:
    hit = _mock_hit()
    hit["_source"]["metadata"] = {
        "title": [{"value": "Gemappter Titel", "lang": "de"}],
        "photographer": [{"value": "Ada Lovelace"}],
    }
    mapping_index = {
        "object": {
            "title": ["dc:title"],
            "photographer": ["dc:creator"],
        }
    }

    xml = oaipmh_service.get_record(
        hit,
        "http://test/oai",
        "oai:katalon:object:550e8400",
        "oai_dc",
        OAI_DC,
        mapping_index,
    )

    assert "<dc:title>Gemappter Titel</dc:title>" in xml
    assert "<dc:creator>Ada Lovelace</dc:creator>" in xml
    identifier = f"oai:{settings.oai_repository_domain}:object:550e8400-e29b-41d4-a716-446655440000"
    assert f"<dc:identifier>{identifier}</dc:identifier>" in xml


def test_get_record_repeatable_mapping_emits_multiple_dc_elements() -> None:
    hit = _mock_hit()
    hit["_source"]["metadata"] = {"keywords": ["Fotografie", "Marrakesch"]}
    mapping_index = {"object": {"keywords": ["dc:subject"]}}

    xml = oaipmh_service.get_record(
        hit,
        "http://test/oai",
        "oai:katalon:object:550e8400",
        "oai_dc",
        OAI_DC,
        mapping_index,
    )

    assert "<dc:subject>Fotografie</dc:subject>" in xml
    assert "<dc:subject>Marrakesch</dc:subject>" in xml


def test_list_records_empty_returns_noRecordsMatch() -> None:
    xml = oaipmh_service.list_records([], 0, 0, None, None, None, "oai_dc", "http://test/oai", OAI_DC)
    assert "noRecordsMatch" in xml


def test_token_roundtrip() -> None:
    token = oaipmh_service.encode_token(
        offset=100,
        set_spec="object",
        from_="2024-01-01",
        until="2024-12-31",
        prefix="oai_dc",
    )
    decoded = oaipmh_service.decode_token(token)
    assert decoded["offset"] == 100
    assert decoded["set_spec"] == "object"
    assert decoded["from_"] == "2024-01-01"
    assert decoded["until"] == "2024-12-31"
    assert decoded["prefix"] == "oai_dc"


def test_token_roundtrip_none_values() -> None:
    token = oaipmh_service.encode_token(
        offset=0,
        set_spec=None,
        from_=None,
        until=None,
        prefix="oai_dc",
    )
    decoded = oaipmh_service.decode_token(token)
    assert decoded["offset"] == 0
    assert decoded["set_spec"] is None
    assert decoded["from_"] is None
    assert decoded["until"] is None
    assert decoded["prefix"] == "oai_dc"


def test_list_records_with_resumption_token() -> None:
    hit = _mock_hit()
    xml = oaipmh_service.list_records(
        [hit], total=200, offset=0, set_spec=None,
        from_=None, until=None, prefix="oai_dc", base_url="http://test/oai", metadata_format=OAI_DC
    )
    assert "resumptionToken" in xml
    assert 'completeListSize="200"' in xml
    assert 'cursor="0"' in xml
    # Token text should be present (next offset = 1)
    root = ET.fromstring(xml.split("\n", 1)[-1] if xml.startswith("<?") else xml)
    rt = root.find(".//{http://www.openarchives.org/OAI/2.0/}resumptionToken")
    assert rt is not None
    assert rt.text is not None
    decoded = oaipmh_service.decode_token(rt.text)
    assert decoded["offset"] == 1


def test_list_records_last_page_empty_token() -> None:
    hit = _mock_hit()
    xml = oaipmh_service.list_records(
        [hit], total=1, offset=0, set_spec=None,
        from_=None, until=None, prefix="oai_dc", base_url="http://test/oai", metadata_format=OAI_DC
    )
    # Last page: resumptionToken element present but empty (no text)
    assert "resumptionToken" in xml
    root = ET.fromstring(xml.split("\n", 1)[-1] if xml.startswith("<?") else xml)
    rt = root.find(".//{http://www.openarchives.org/OAI/2.0/}resumptionToken")
    assert rt is not None
    assert rt.text is None or rt.text == ""


def _mock_hit_n(n: int) -> dict:
    hit = _mock_hit()
    hit["_id"] = f"550e8400-e29b-41d4-a716-4466554400{n:02d}"
    hit["_source"]["idno"] = f"TEST-{n:03d}"
    return hit


def test_list_records_resumption_token_roundtrip_across_pages() -> None:
    total = 5
    page_size = 2
    all_hits = [_mock_hit_n(n) for n in range(total)]

    seen_ids: list[str] = []
    offset = 0
    token: str | None = ""
    pages = 0
    while token is not None:
        page_hits = all_hits[offset : offset + page_size]
        xml = oaipmh_service.list_records(
            page_hits, total=total, offset=offset, set_spec=None,
            from_=None, until=None, prefix="oai_dc", base_url="http://test/oai", metadata_format=OAI_DC
        )
        root = ET.fromstring(xml.split("\n", 1)[-1] if xml.startswith("<?") else xml)
        seen_ids.extend(
            e.text
            for e in root.findall(".//{http://www.openarchives.org/OAI/2.0/}identifier")
        )
        rt = root.find(".//{http://www.openarchives.org/OAI/2.0/}resumptionToken")
        assert rt is not None
        token = rt.text
        pages += 1
        if token:
            decoded = oaipmh_service.decode_token(token)
            offset = decoded["offset"]
        assert pages <= total  # guard against infinite loop on a broken pagination contract

    assert len(seen_ids) == total
    assert len(set(seen_ids)) == total
    assert pages == 3  # ceil(5 / 2)


def test_list_identifiers_with_resumption_token() -> None:
    hit = _mock_hit()
    xml = oaipmh_service.list_identifiers(
        [hit], total=200, offset=0, set_spec=None,
        from_=None, until=None, prefix="oai_dc", base_url="http://test/oai"
    )
    assert "resumptionToken" in xml
    root = ET.fromstring(xml.split("\n", 1)[-1] if xml.startswith("<?") else xml)
    rt = root.find(".//{http://www.openarchives.org/OAI/2.0/}resumptionToken")
    assert rt is not None
    assert rt.text is not None
    decoded = oaipmh_service.decode_token(rt.text)
    assert decoded["offset"] == 1


def test_oaipmh_with_json_ld_format() -> None:
    json_ld_fmt = JsonLdFormat()
    xml = oaipmh_service.list_metadata_formats("http://test/oai", [OAI_DC, json_ld_fmt])
    assert "json_ld" in xml
    assert "http://www.w3.org/ns/json-ld" in xml

    hit = _mock_hit()
    record_xml = oaipmh_service.get_record(
        hit, "http://test/oai", "oai:katalon:object:550e8400", "json_ld", json_ld_fmt
    )
    assert "<json_ld" in record_xml
    assert "crm:E22_Human-Made_Object" in record_xml or "lrmoo:F5_Item" in record_xml
