from unittest.mock import AsyncMock, patch

import pytest

from katalon.integrations.geonames_adapter import GeonamesAdapter
from katalon.integrations.gnd_adapter import GNDAdapter
from katalon.integrations.iconclass_adapter import ICONCLASSAdapter
from katalon.integrations.tgn_adapter import TGNAdapter
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


# ── Geonames ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_geonames_search_parses_results() -> None:
    data = {"geonames": [
        {
            "geonameId": 2950159,
            "name": "Berlin",
            "countryName": "Germany",
            "fclName": "city, village,...",
            "fcl": "P",
            "lat": "52.52437",
            "lng": "13.41053",
        }
    ]}
    with patch("katalon.integrations.geonames_adapter.httpx.AsyncClient", _http(data)):
        hits = await GeonamesAdapter().search("berlin")
    assert len(hits) == 1
    assert hits[0].external_id == "2950159"
    assert hits[0].label == "Berlin"
    assert "Germany" in hits[0].description
    assert hits[0].extra["lat"] == "52.52437"
    assert hits[0].source == "geonames"


@pytest.mark.asyncio
async def test_geonames_search_empty_returns_empty() -> None:
    with patch("katalon.integrations.geonames_adapter.httpx.AsyncClient", _http({"geonames": []})):
        hits = await GeonamesAdapter().search("xyz")
    assert hits == []


@pytest.mark.asyncio
async def test_geonames_fetch_returns_hit() -> None:
    data = {
        "name": "Berlin",
        "fclName": "Hauptstadt",
        "lat": "52.52437",
        "lng": "13.41053",
        "countryName": "Germany",
    }
    with patch("katalon.integrations.geonames_adapter.httpx.AsyncClient", _http(data)):
        hit = await GeonamesAdapter().fetch("2950159")
    assert hit is not None
    assert hit.label == "Berlin"
    assert hit.description == "Hauptstadt"
    assert hit.extra["countryName"] == "Germany"


@pytest.mark.asyncio
async def test_geonames_fetch_404_returns_none() -> None:
    with patch("katalon.integrations.geonames_adapter.httpx.AsyncClient", _http({}, status=404)):
        hit = await GeonamesAdapter().fetch("99999")
    assert hit is None


@pytest.mark.asyncio
async def test_geonames_fetch_status_error_returns_none() -> None:
    data = {"status": {"message": "the user does not exist.", "value": 10}}
    with patch("katalon.integrations.geonames_adapter.httpx.AsyncClient", _http(data)):
        hit = await GeonamesAdapter().fetch("99999")
    assert hit is None


# ── TGN ───────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tgn_search_parses_bindings() -> None:
    data = {
        "results": {
            "bindings": [
                {
                    "place": {"value": "http://vocab.getty.edu/tgn/7003712"},
                    "label": {"value": "Marrakech"},
                    "lat": {"value": "31.63416"},
                    "long": {"value": "-8.00028"},
                }
            ]
        }
    }
    with patch("katalon.integrations.tgn_adapter.httpx.AsyncClient", _http(data)):
        hits = await TGNAdapter().search("marrakesch")
    assert len(hits) == 1
    assert hits[0].external_id == "7003712"
    assert hits[0].label == "Marrakech"
    assert hits[0].extra["lat"] == "31.63416"
    assert hits[0].source == "tgn"


@pytest.mark.asyncio
async def test_tgn_search_empty_bindings_returns_empty() -> None:
    data = {"results": {"bindings": []}}
    with patch("katalon.integrations.tgn_adapter.httpx.AsyncClient", _http(data)):
        hits = await TGNAdapter().search("xyz")
    assert hits == []


@pytest.mark.asyncio
async def test_tgn_fetch_parses_graph_prefers_german() -> None:
    data = {
        "@graph": [
            {
                "@id": "http://vocab.getty.edu/tgn/7003712",
                "skos:prefLabel": [
                    {"@value": "Marrakesch", "@language": "de"},
                    {"@value": "Marrakech", "@language": "en"},
                ],
            }
        ]
    }
    with patch("katalon.integrations.tgn_adapter.httpx.AsyncClient", _http(data)):
        hit = await TGNAdapter().fetch("7003712")
    assert hit is not None
    assert hit.label == "Marrakesch"
    assert hit.external_id == "7003712"
    assert hit.source == "tgn"


@pytest.mark.asyncio
async def test_tgn_fetch_404_returns_none() -> None:
    with patch("katalon.integrations.tgn_adapter.httpx.AsyncClient", _http({}, status=404)):
        hit = await TGNAdapter().fetch("9999999")
    assert hit is None


# ── ICONCLASS ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_iconclass_fetch_prefers_german_label() -> None:
    data = {
        "txt": {"de": ["Madonna mit Kind"], "en": ["Madonna with Child"]},
        "kw": {"de": ["Kunst", "Religion"]},
        "p": ["71A"],
    }
    with patch("katalon.integrations.iconclass_adapter.httpx.AsyncClient", _http(data)):
        hit = await ICONCLASSAdapter().fetch("71A1")
    assert hit is not None
    assert hit.label == "Madonna mit Kind"
    assert "Kunst" in hit.description
    assert hit.extra["broader"] == ["71A"]
    assert hit.source == "iconclass"


@pytest.mark.asyncio
async def test_iconclass_fetch_fallback_to_english() -> None:
    data = {
        "txt": {"en": ["Madonna with Child"]},
        "kw": {},
        "p": [],
    }
    with patch("katalon.integrations.iconclass_adapter.httpx.AsyncClient", _http(data)):
        hit = await ICONCLASSAdapter().fetch("71A1")
    assert hit is not None
    assert hit.label == "Madonna with Child"


@pytest.mark.asyncio
async def test_iconclass_fetch_not_found_returns_none() -> None:
    with patch("katalon.integrations.iconclass_adapter.httpx.AsyncClient", _http({}, status=404)):
        hit = await ICONCLASSAdapter().fetch("9999")
    assert hit is None


@pytest.mark.asyncio
async def test_iconclass_search_fetches_details_for_first_five() -> None:
    adapter = ICONCLASSAdapter()
    search_data = {"result": ["71A1", "71A2", "71A3"]}
    detail_hit = AsyncMock(return_value=_http({"txt": {"de": ["Detail"]}, "kw": {}, "p": []}))

    from katalon.integrations.authority import AuthorityHit
    fake_detail = AuthorityHit(source="iconclass", external_id="71A1", label="Detail", description="")

    with patch("katalon.integrations.iconclass_adapter.httpx.AsyncClient", _http(search_data)):
        with patch.object(adapter, "_fetch_notation", AsyncMock(return_value=fake_detail)):
            hits = await adapter.search("madonna")

    assert len(hits) == 3
    assert all(h.label == "Detail" for h in hits)


@pytest.mark.asyncio
async def test_iconclass_search_stubs_beyond_five() -> None:
    adapter = ICONCLASSAdapter()
    notations = [f"7{i}A1" for i in range(7)]
    search_data = {"result": notations}

    from katalon.integrations.authority import AuthorityHit
    fake_detail = AuthorityHit(source="iconclass", external_id="x", label="Detail", description="")

    with patch("katalon.integrations.iconclass_adapter.httpx.AsyncClient", _http(search_data)):
        with patch.object(adapter, "_fetch_notation", AsyncMock(return_value=fake_detail)) as mock_fetch:
            hits = await adapter.search("test")

    assert len(hits) == 7
    assert mock_fetch.call_count == 5
    detail_hits = [h for h in hits if h.label == "Detail"]
    stub_hits = [h for h in hits if h.label != "Detail"]
    assert len(detail_hits) == 5
    assert len(stub_hits) == 2
