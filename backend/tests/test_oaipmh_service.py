import xml.etree.ElementTree as ET
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone

from katalon.services import oaipmh_service


def test_identify_contains_repository_name() -> None:
    xml = oaipmh_service.identify("http://test/oai")
    root = ET.fromstring(xml.split("\n", 1)[-1] if xml.startswith("<?") else xml)
    names = root.findall(".//{http://www.openarchives.org/OAI/2.0/}repositoryName")
    assert any("Katalon" in n.text for n in names if n.text)


def test_list_sets_contains_four_sets() -> None:
    xml = oaipmh_service.list_sets()
    root = ET.fromstring(xml.split("\n", 1)[-1] if xml.startswith("<?") else xml)
    specs = root.findall(".//{http://www.openarchives.org/OAI/2.0/}setSpec")
    assert {s.text for s in specs} >= {"object", "entity", "place", "occurrence"}


def test_bad_verb() -> None:
    xml = oaipmh_service.bad_verb("Nonsense")
    assert "badVerb" in xml


def _mock_record() -> MagicMock:
    rec = MagicMock()
    rec.id = "550e8400-e29b-41d4-a716-446655440000"
    rec.metadata_ = {"title": [{"value": "Test Foto"}]}
    rec.idno = "TEST-001"
    rec.created_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    rec.updated_at = datetime(2024, 6, 1, tzinfo=timezone.utc)
    return rec


def test_get_record_contains_dc_title() -> None:
    rec = _mock_record()
    xml = oaipmh_service.get_record(rec, "object", "http://test/oai")
    assert "Test Foto" in xml


def test_list_records_empty_returns_noRecordsMatch() -> None:
    xml = oaipmh_service.list_records([], "object", "http://test/oai")
    assert "noRecordsMatch" in xml
