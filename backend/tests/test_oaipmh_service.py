import xml.etree.ElementTree as ET
from types import SimpleNamespace

from katalon.services import oaipmh_service


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


def test_get_record_contains_dc_title() -> None:
    hit = _mock_hit()
    xml = oaipmh_service.get_record(hit, "http://test/oai", "oai:katalon:object:550e8400", "oai_dc")
    assert "Test Foto" in xml


def test_list_records_empty_returns_noRecordsMatch() -> None:
    xml = oaipmh_service.list_records([], 0, 0, None, None, None, "oai_dc", "http://test/oai")
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
        from_=None, until=None, prefix="oai_dc", base_url="http://test/oai"
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
        from_=None, until=None, prefix="oai_dc", base_url="http://test/oai"
    )
    # Last page: resumptionToken element present but empty (no text)
    assert "resumptionToken" in xml
    root = ET.fromstring(xml.split("\n", 1)[-1] if xml.startswith("<?") else xml)
    rt = root.find(".//{http://www.openarchives.org/OAI/2.0/}resumptionToken")
    assert rt is not None
    assert rt.text is None or rt.text == ""


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
