import pytest
from unittest.mock import patch

from katalon.integrations.gnd_adapter import GNDAdapter
from katalon.integrations.viaf_adapter import VIAFAdapter
from katalon.integrations.wikidata_adapter import WikidataAdapter


class _Response:
    def __init__(self, data: dict, status: int = 200) -> None:
        self.status_code = status
        self._data = data

    def json(self) -> dict:
        return self._data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


def _http(data: dict, status: int = 200):
    """Returns a class suitable for replacing httpx.AsyncClient."""

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def get(self, *args, **kwargs) -> _Response:
            return _Response(data, status)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            pass

    return FakeAsyncClient


# ── GND ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_gnd_search_parses_members() -> None:
    data = {"member": [
        {
            "gndIdentifier": "118508237",
            "preferredName": "Beethoven, Ludwig van",
            "professionOrOccupation": [{"label": "Komponist"}],
        }
    ]}
    with patch("katalon.integrations.gnd_adapter.httpx.AsyncClient", _http(data)):
        hits = await GNDAdapter().search("beethoven")
    assert len(hits) == 1
    assert hits[0].external_id == "118508237"
    assert hits[0].label == "Beethoven, Ludwig van"
    assert hits[0].description == "Komponist"
    assert hits[0].source == "gnd"


@pytest.mark.asyncio
async def test_gnd_search_empty_member_list() -> None:
    with patch("katalon.integrations.gnd_adapter.httpx.AsyncClient", _http({"member": []})):
        hits = await GNDAdapter().search("xyz")
    assert hits == []


@pytest.mark.asyncio
async def test_gnd_search_multiple_professions() -> None:
    data = {"member": [
        {
            "gndIdentifier": "118508237",
            "preferredName": "Beethoven, Ludwig van",
            "professionOrOccupation": [{"label": "Komponist"}, {"label": "Pianist"}, {"label": "Dirigent"}],
        }
    ]}
    with patch("katalon.integrations.gnd_adapter.httpx.AsyncClient", _http(data)):
        hits = await GNDAdapter().search("beethoven")
    assert "Komponist" in hits[0].description
    assert "Pianist" in hits[0].description


@pytest.mark.asyncio
async def test_gnd_fetch_returns_hit() -> None:
    data = {
        "preferredName": "Beethoven, Ludwig van",
        "biographicalOrHistoricalInformation": ["Deutscher Komponist"],
    }
    with patch("katalon.integrations.gnd_adapter.httpx.AsyncClient", _http(data)):
        hit = await GNDAdapter().fetch("118508237")
    assert hit is not None
    assert hit.label == "Beethoven, Ludwig van"
    assert hit.description == "Deutscher Komponist"
    assert hit.external_id == "118508237"


@pytest.mark.asyncio
async def test_gnd_fetch_without_bio_info() -> None:
    data = {"preferredName": "Beethoven, Ludwig van"}
    with patch("katalon.integrations.gnd_adapter.httpx.AsyncClient", _http(data)):
        hit = await GNDAdapter().fetch("118508237")
    assert hit is not None
    assert hit.description == ""


@pytest.mark.asyncio
async def test_gnd_fetch_404_returns_none() -> None:
    with patch("katalon.integrations.gnd_adapter.httpx.AsyncClient", _http({}, status=404)):
        hit = await GNDAdapter().fetch("nonexistent")
    assert hit is None


# ── VIAF ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_viaf_search_parses_results() -> None:
    data = {"result": [
        {"viafid": "32182557", "term": "Beethoven, Ludwig van", "nametype": "Personal"}
    ]}
    with patch("katalon.integrations.viaf_adapter.httpx.AsyncClient", _http(data)):
        hits = await VIAFAdapter().search("beethoven")
    assert len(hits) == 1
    assert hits[0].external_id == "32182557"
    assert hits[0].label == "Beethoven, Ludwig van"
    assert hits[0].description == "Personal"
    assert hits[0].source == "viaf"
    assert hits[0].extra["uri"] == "https://viaf.org/viaf/32182557"


@pytest.mark.asyncio
async def test_viaf_search_null_result_returns_empty() -> None:
    with patch("katalon.integrations.viaf_adapter.httpx.AsyncClient", _http({"result": None})):
        hits = await VIAFAdapter().search("xyz")
    assert hits == []


@pytest.mark.asyncio
async def test_viaf_search_respects_limit() -> None:
    data = {"result": [{"viafid": str(i), "term": f"Name {i}", "nametype": "Personal"} for i in range(20)]}
    with patch("katalon.integrations.viaf_adapter.httpx.AsyncClient", _http(data)):
        hits = await VIAFAdapter().search("name", limit=3)
    assert len(hits) == 3


@pytest.mark.asyncio
async def test_viaf_fetch_returns_hit() -> None:
    data = {
        "mainHeadings": {"data": [{"text": "Beethoven, Ludwig van"}]},
        "nameType": "Personal",
    }
    with patch("katalon.integrations.viaf_adapter.httpx.AsyncClient", _http(data)):
        hit = await VIAFAdapter().fetch("32182557")
    assert hit is not None
    assert hit.label == "Beethoven, Ludwig van"
    assert hit.description == "Personal"


@pytest.mark.asyncio
async def test_viaf_fetch_empty_headings() -> None:
    data = {"mainHeadings": {"data": []}, "nameType": "Corporate"}
    with patch("katalon.integrations.viaf_adapter.httpx.AsyncClient", _http(data)):
        hit = await VIAFAdapter().fetch("99999")
    assert hit is not None
    assert hit.label == ""


@pytest.mark.asyncio
async def test_viaf_fetch_404_returns_none() -> None:
    with patch("katalon.integrations.viaf_adapter.httpx.AsyncClient", _http({}, status=404)):
        hit = await VIAFAdapter().fetch("nonexistent")
    assert hit is None


# ── Wikidata ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_wikidata_search_parses_items() -> None:
    data = {"search": [
        {"id": "Q2993", "label": "Beethoven", "description": "Komponist"}
    ]}
    with patch("katalon.integrations.wikidata_adapter.httpx.AsyncClient", _http(data)):
        hits = await WikidataAdapter().search("beethoven")
    assert len(hits) == 1
    assert hits[0].external_id == "Q2993"
    assert hits[0].label == "Beethoven"
    assert hits[0].description == "Komponist"
    assert hits[0].source == "wikidata"
    assert hits[0].extra["uri"] == "https://www.wikidata.org/wiki/Q2993"


@pytest.mark.asyncio
async def test_wikidata_search_empty_returns_empty() -> None:
    with patch("katalon.integrations.wikidata_adapter.httpx.AsyncClient", _http({"search": []})):
        hits = await WikidataAdapter().search("xyz")
    assert hits == []


@pytest.mark.asyncio
async def test_wikidata_fetch_prefers_german_label() -> None:
    data = {
        "entities": {
            "Q2993": {
                "labels": {
                    "en": {"value": "Beethoven (English)"},
                    "de": {"value": "Beethoven (Deutsch)"},
                },
                "descriptions": {"de": {"value": "Komponist"}},
            }
        }
    }
    with patch("katalon.integrations.wikidata_adapter.httpx.AsyncClient", _http(data)):
        hit = await WikidataAdapter().fetch("Q2993")
    assert hit is not None
    assert hit.label == "Beethoven (Deutsch)"
    assert hit.description == "Komponist"


@pytest.mark.asyncio
async def test_wikidata_fetch_falls_back_to_english() -> None:
    data = {
        "entities": {
            "Q2993": {
                "labels": {"en": {"value": "Beethoven (English)"}},
                "descriptions": {},
            }
        }
    }
    with patch("katalon.integrations.wikidata_adapter.httpx.AsyncClient", _http(data)):
        hit = await WikidataAdapter().fetch("Q2993")
    assert hit is not None
    assert hit.label == "Beethoven (English)"


@pytest.mark.asyncio
async def test_wikidata_fetch_404_returns_none() -> None:
    with patch("katalon.integrations.wikidata_adapter.httpx.AsyncClient", _http({}, status=404)):
        hit = await WikidataAdapter().fetch("Q99999")
    assert hit is None
