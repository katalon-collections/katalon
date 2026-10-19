# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""LIDO export for the DDB: golden file, round trip and the configurable structures."""

from __future__ import annotations

import json
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

from katalon.core.models import ExportMappingRule, ExportMappingSet
from katalon.integrations.authority_uris import authority_uri, parse_authority_url
from katalon.integrations.licenses import is_allowed_license, license_label, normalize_license_uri
from katalon.integrations.lido.builder import (
    LIDO_NS,
    date_limits,
    format_date_display,
    parse_measurement,
)
from katalon.integrations.lido.validator import validate_lido_xml
from katalon.integrations.lido_format import LidoFormat
from katalon.integrations.metadata_format import (
    CompiledMappingSet,
    ExportMediaItem,
    ExportRecordContext,
    ExportRecordSummary,
    ExportRelation,
    MappingSpec,
    SourceKind,
)
from katalon.services import metadata_mapping_service
from katalon.services.metadata_mapping_service import compile_mapping_set

FIXTURES = Path(__file__).resolve().parent / "fixtures"
NS = {"lido": LIDO_NS}
L = f"{{{LIDO_NS}}}"


def _mapping_from_yaml(text: str) -> CompiledMappingSet:
    data = yaml.safe_load(text)
    rules = []
    for raw in data["rules"]:
        config = dict(raw.get("source_config") or {})
        if raw.get("field_name"):
            config["field_name"] = raw["field_name"]
        rules.append(
            MappingSpec(
                source_kind=SourceKind(raw.get("source_kind", "field")),
                source_config=config,
                target_key=raw["target_key"],
                settings=dict(raw.get("settings") or {}),
                sort_order=int(raw.get("sort_order", 0)),
                is_enabled=bool(raw.get("is_enabled", True)),
            )
        )
    return CompiledMappingSet(
        format_key="lido",
        record_type="object",
        rules=sorted(rules, key=lambda r: r.sort_order),
        institution_config=data.get("institution_config") or {},
    )


@pytest.fixture
def ddb_mapping() -> CompiledMappingSet:
    return _mapping_from_yaml((FIXTURES / "lido_ddb_mapping.yaml").read_text(encoding="utf-8"))


@pytest.fixture
def ddb_context() -> ExportRecordContext:
    data = json.loads((FIXTURES / "lido_ddb_os_ub_0031153.json").read_text(encoding="utf-8"))
    return ExportRecordContext.model_validate(data)


def _render(ctx: ExportRecordContext, cms: CompiledMappingSet) -> str:
    return ET.tostring(LidoFormat().render(ctx, cms), encoding="unicode")


def _canonical(xml: str) -> str:
    return ET.canonicalize(xml, strip_text=True, with_comments=False)


def _minimal(extra: list[MappingSpec] | None = None, config: dict[str, Any] | None = None) -> CompiledMappingSet:
    return CompiledMappingSet(
        format_key="lido",
        record_type="object",
        rules=[
            MappingSpec(source_kind=SourceKind.RECORD, source_config={"property": "title"},
                        target_key="lido:objectIdentificationWrap/lido:titleWrap/lido:titleSet/lido:appellationValue"),
            MappingSpec(source_kind=SourceKind.CONSTANT, source_config={"value": "Postkarte"},
                        target_key="lido:objectClassificationWrap/lido:objectWorkTypeWrap/lido:objectWorkType"),
            *(extra or []),
        ],
        institution_config=config or {},
    )


def _ctx(**kwargs: Any) -> ExportRecordContext:
    return ExportRecordContext(
        record=ExportRecordSummary(id="obj-1", idno="INV-1", record_type="object", title="Titel",
                                   updated_at="2026-10-01T10:00:00"),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Golden file / round trip
# ---------------------------------------------------------------------------


def test_golden_record_matches_target_xml_and_validates(
    ddb_context: ExportRecordContext, ddb_mapping: CompiledMappingSet
) -> None:
    xml = _render(ddb_context, ddb_mapping)
    assert validate_lido_xml(xml) == []
    assert LidoFormat().required_field_errors(ddb_context, ddb_mapping) == []
    expected = (FIXTURES / "lido_ddb_os_ub_0031153.xml").read_text(encoding="utf-8")
    assert _canonical(xml) == _canonical(expected)


@pytest.mark.asyncio
async def test_yaml_import_export_import_renders_identically(
    ddb_context: ExportRecordContext, ddb_mapping: CompiledMappingSet
) -> None:
    yaml_text = (FIXTURES / "lido_ddb_mapping.yaml").read_text(encoding="utf-8")
    names = {r["field_name"] for r in yaml.safe_load(yaml_text)["rules"] if r.get("field_name")}
    field_defs = []
    for name in {part for n in names for part in n.split(".")}:
        fd = MagicMock()
        fd.id = uuid.uuid4()
        fd.name = name
        fd.field_type = "group" if name == "beschriftung_gedruckt" else "text"
        field_defs.append(fd)

    async def import_yaml(text: str) -> ExportMappingSet:
        added: list[object] = []
        db = AsyncMock()
        db.add = MagicMock(side_effect=added.append)
        revs, pub, fields = MagicMock(), MagicMock(), MagicMock()
        revs.scalars.return_value.all.return_value = []
        pub.scalar_one_or_none.return_value = None
        fields.scalars.return_value.all.return_value = field_defs
        refresh = MagicMock()
        refresh.scalar_one_or_none.return_value = None
        db.execute.side_effect = [revs, pub, fields, refresh]
        _set, warnings, _count = await metadata_mapping_service.import_mapping_set_from_yaml(db, text)
        assert warnings == []
        mapping_set = next(x for x in added if isinstance(x, ExportMappingSet))
        mapping_set.id = uuid.uuid4()
        mapping_set.rules = [x for x in added if isinstance(x, ExportMappingRule)]
        for rule in mapping_set.rules:
            rule.id = uuid.uuid4()
            rule.field_definition = None
        return mapping_set

    first = await import_yaml(yaml_text)
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = first
    db.execute.return_value = result
    exported, _filename = await metadata_mapping_service.export_mapping_set_to_yaml(db, first.id)
    second = await import_yaml(exported)

    original = _render(ddb_context, ddb_mapping)
    assert _render(ddb_context, compile_mapping_set(first)) == original
    assert _render(ddb_context, compile_mapping_set(second)) == original
    assert "beschriftung_gedruckt.beschriftung_gedruck_vorder" in exported


def test_existing_mapping_without_new_settings_still_validates() -> None:
    """Old-style mapping (legacy targets, no profile): valid LIDO, URIs instead of words."""
    cms = _minimal([
        MappingSpec(source_kind=SourceKind.FIELD, source_config={"field_name": "beschreibung"},
                    target_key="lido:objectIdentificationWrap/lido:objectDescriptionWrap/lido:objectDescriptionSet/lido:descriptiveNoteValue/short"),
        MappingSpec(source_kind=SourceKind.FIELD, source_config={"field_name": "masse"},
                    target_key="lido:objectIdentificationWrap/lido:objectMeasurementsWrap/lido:objectMeasurementsSet/lido:displayObjectMeasurements"),
        MappingSpec(source_kind=SourceKind.FIELD, source_config={"field_name": "material"},
                    target_key="lido:eventWrap/lido:eventSet/lido:event/lido:eventMaterialsTech/lido:displayMaterialsTech"),
        MappingSpec(source_kind=SourceKind.MEDIA, source_config={"property": "url"},
                    target_key="lido:administrativeMetadata/lido:resourceWrap/lido:resourceSet/lido:resourceRepresentation/lido:linkResource"),
    ], {"institution_name": "Museum", "location": "Ort"})
    ctx = _ctx(
        fields={"beschreibung": "Kurz", "masse": "10 x 15 cm", "material": "Papier"},
        media=[ExportMediaItem(id="m1", filename="a.jpg", mime_type="image/jpeg", url="https://x/a.jpg")],
    )
    xml = _render(ctx, cms)
    assert validate_lido_xml(xml) == []
    root = ET.fromstring(xml)
    assert root.find(".//lido:repositorySet", NS).attrib[f"{L}type"].endswith("lido00475")
    assert root.find(".//lido:titleSet/lido:appellationValue", NS).attrib[f"{L}pref"].endswith("lido00169")
    assert root.find(".//lido:objectDescriptionSet", NS).attrib[f"{L}type"] == "brief"
    assert root.findtext(".//lido:linkResource", namespaces=NS) == "https://x/a.jpg"


# ---------------------------------------------------------------------------
# General output rules
# ---------------------------------------------------------------------------


def test_values_are_trimmed_and_empty_values_create_no_elements() -> None:
    cms = _minimal([
        MappingSpec(source_kind=SourceKind.FIELD, source_config={"field_name": "beschreibung"},
                    target_key="lido:objectIdentificationWrap/lido:objectDescriptionWrap/lido:objectDescriptionSet/lido:descriptiveNoteValue"),
        MappingSpec(source_kind=SourceKind.FIELD, source_config={"field_name": "inschrift"},
                    target_key="lido:objectIdentificationWrap/lido:inscriptionsWrap/lido:inscriptions/lido:inscriptionTranscription"),
    ])
    xml = _render(_ctx(fields={"beschreibung": "   <p>&nbsp;</p>\n", "inschrift": "Text \n"}), cms)
    assert validate_lido_xml(xml) == []
    assert "objectDescriptionWrap" not in xml
    assert ">Text<" in xml
    assert "<lido:recordMetadataDate />" not in xml


def test_html_line_breaks_inside_words_do_not_glue_words() -> None:
    cms = _minimal([MappingSpec(source_kind=SourceKind.FIELD, source_config={"field_name": "t"},
                                target_key="lido:objectIdentificationWrap/lido:inscriptionsWrap/lido:inscriptions/lido:inscriptionTranscription")])
    xml = _render(_ctx(fields={"t": "Unter<br/>land &amp; Ober<br />land"}), cms)
    assert ">Unter land &amp; Ober land<" in xml


def test_vocabulary_qualifiers_in_angle_brackets_survive() -> None:
    cms = _minimal([MappingSpec(source_kind=SourceKind.FIELD, source_config={"field_name": "s"},
                                target_key="lido:objectRelationWrap/lido:subjectWrap/lido:subjectSet/lido:subject/lido:subjectConcept/lido:term")])
    xml = _render(_ctx(fields={"s": [{"label": "Himmel < religiös >"}, "Himmel < naturwissenschaftlich >",
                                     "<em>Volkslied</em> < deutsch >"]}), cms)
    assert "<lido:term>Himmel &lt; religiös &gt;</lido:term>" in xml
    assert "<lido:term>Himmel &lt; naturwissenschaftlich &gt;</lido:term>" in xml
    assert "<lido:term>Volkslied &lt; deutsch &gt;</lido:term>" in xml


def test_identical_repetitions_are_deduplicated() -> None:
    cms = _minimal([MappingSpec(source_kind=SourceKind.FIELD, source_config={"field_name": "s"},
                                target_key="lido:objectRelationWrap/lido:subjectWrap/lido:subjectSet/lido:subject/lido:subjectConcept/lido:term")])
    root = ET.fromstring(_render(_ctx(fields={"s": ["Wald", "Wald ", "Baum"]}), cms))
    assert [t.text for t in root.iterfind(".//lido:subjectConcept/lido:term", NS)] == ["Wald", "Baum"]


def test_record_without_title_is_rejected() -> None:
    ctx = ExportRecordContext(record=ExportRecordSummary(id="x", record_type="object"))
    errors = LidoFormat().required_field_errors(ctx, _minimal())
    assert "Objekttitel (appellationValue) ist leer" in errors
    assert "titleWrap" not in _render(ctx, _minimal())


def test_record_metadata_date_uses_created_at_when_never_updated() -> None:
    ctx = ExportRecordContext(record=ExportRecordSummary(
        id="x", record_type="object", title="T", created_at="2026-01-01T00:00:00"))
    el = ET.fromstring(_render(ctx, _minimal())).find(".//lido:recordMetadataDate", NS)
    assert el.text == "2026-01-01T00:00:00"
    assert el.attrib[f"{L}type"].endswith("lido00470")


# ---------------------------------------------------------------------------
# Authority URIs and licenses
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("source", "ident", "expected"), [
    ("geonames", "2950159", "https://sws.geonames.org/2950159/"),
    ("gnd", "116785861", "https://d-nb.info/gnd/116785861"),
    ("gnd-person", "116785861", "https://d-nb.info/gnd/116785861"),
    ("wikidata", "Q2060171", "http://www.wikidata.org/entity/Q2060171"),
    ("aat", "300008707", "http://vocab.getty.edu/aat/300008707"),
    ("tgn", "7005252", "http://vocab.getty.edu/tgn/7005252"),
    ("ulan", "500115493", "http://vocab.getty.edu/ulan/500115493"),
    ("viaf", "12345", "http://viaf.org/viaf/12345"),
    ("iconclass", "25G3", "https://iconclass.org/25G3"),
    ("iconclass", "de", None),
    ("unknown", "1", None),
])
def test_authority_uri(source: str, ident: str, expected: str | None) -> None:
    assert authority_uri(source, ident) == expected


def test_geonames_uris_always_end_with_slash() -> None:
    for url in ("https://sws.geonames.org/2950159", "http://www.geonames.org/2950159/berlin.html"):
        assert parse_authority_url(url) == ("geonames", "https://sws.geonames.org/2950159/")


def test_authority_urls_are_normalized() -> None:
    assert parse_authority_url("http://d-nb.info/gnd/116785861") == ("gnd", "https://d-nb.info/gnd/116785861")
    assert parse_authority_url("https://www.wikidata.org/wiki/Q42") == ("wikidata", "http://www.wikidata.org/entity/Q42")


def test_license_spelling_is_kept_unless_an_allowed_list_says_otherwise() -> None:
    stored = "https://creativecommons.org/licenses/by/4.0"
    # No preferred spelling in the core.
    assert normalize_license_uri(stored) == stored
    allowed = ["http://creativecommons.org/licenses/by/4.0/"]
    assert normalize_license_uri(stored, allowed) == "http://creativecommons.org/licenses/by/4.0/"
    assert license_label("https://creativecommons.org/licenses/by-nc-sa/4.0") == "CC BY-NC-SA 4.0"
    assert is_allowed_license("http://creativecommons.org/licenses/by/4.0/", allowed)
    assert not is_allowed_license(";CC0 1.0;9494", allowed)


# ---------------------------------------------------------------------------
# Dates, measurements, events
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("value", "limits", "display"), [
    ("1905/", ("1905", None), "nach 1905"),
    ("/1910", (None, "1910"), "vor 1910"),
    ("1900-03/1901", ("1900-03", "1901"), "1900-03–1901"),
    ("1900~", ("1900", "1900"), "ca. 1900"),
    ("um 1900", None, None),
])
def test_date_limits_and_display(value: str, limits: Any, display: str | None) -> None:
    assert date_limits(value) == limits
    if display:
        assert format_date_display(value) == display


def test_parse_measurement() -> None:
    assert parse_measurement("9,2 cm") == ("9,2", "9.2", "cm")
    assert parse_measurement("13,9", "cm") == ("13,9", "13.9", "cm")
    assert parse_measurement("ca. 9 x 14 cm") is None
    assert parse_measurement("12") is None


def test_unparsable_measurement_falls_back_to_display_only() -> None:
    cms = _minimal([MappingSpec(source_kind=SourceKind.FIELD, source_config={"field_name": "m"},
                                target_key="lido:objectIdentificationWrap/lido:objectMeasurementsWrap/lido:objectMeasurementsSet/lido:objectMeasurements/lido:measurementsSet",
                                settings={"measurement_type": "Höhe"})])
    xml = _render(_ctx(fields={"m": "ca. 9 x 14 cm"}), cms)
    assert validate_lido_xml(xml) == []
    assert "measurementsSet" not in xml
    assert ">ca. 9 x 14 cm</lido:displayObjectMeasurements>" in xml


def test_event_date_without_end_has_no_latest_date() -> None:
    cms = _minimal([MappingSpec(source_kind=SourceKind.FIELD, source_config={"field_name": "d"},
                                target_key="lido:events/production/date")])
    root = ET.fromstring(_render(_ctx(fields={"d": "1905/"}), cms))
    assert root.findtext(".//lido:earliestDate", namespaces=NS) == "1905"
    assert root.find(".//lido:latestDate", NS) is None


def test_event_places_are_never_joined_and_deduplicated() -> None:
    def place(pid: str, label: str) -> ExportRelation:
        return ExportRelation(id=pid, relation_type="ansaessig", target_type="place", target_id=pid, target_label=label)

    ctx = _ctx(relations=[
        ExportRelation(id="a", relation_type="creator", target_type="entity", target_id="e1", target_label="V1",
                       target_relations=[place("p1", "Berlin")]),
        ExportRelation(id="b", relation_type="creator", target_type="entity", target_id="e2", target_label="V2",
                       target_relations=[place("p1", "Berlin"), place("p2", "Wien")]),
    ])
    cms = _minimal([MappingSpec(source_kind=SourceKind.RELATION,
                                source_config={"relation_type": "creator", "via": {"relation_type": "ansaessig"}},
                                target_key="lido:events/production/place")])
    root = ET.fromstring(_render(ctx, cms))
    assert [p.text for p in root.iterfind(".//lido:displayPlace", NS)] == ["Berlin", "Wien"]


def test_materials_and_techniques_share_one_materials_tech_with_concept_ids() -> None:
    cms = _minimal([
        MappingSpec(source_kind=SourceKind.FIELD, source_config={"field_name": "mat"},
                    target_key="lido:events/production/materials_tech_term", settings={"kind": "material"}),
        MappingSpec(source_kind=SourceKind.FIELD, source_config={"field_name": "tech"},
                    target_key="lido:events/production/materials_tech_term", settings={"kind": "technique"}),
    ])
    ctx = _ctx(fields={"mat": {"id": "t1", "label": "Karton", "uri": "http://vocab.getty.edu/aat/300014224"},
                       "tech": {"id": "t2", "label": "Autotypie"}})
    xml = _render(ctx, cms)
    assert validate_lido_xml(xml) == []
    root = ET.fromstring(xml)
    assert len(root.findall(".//lido:materialsTech", NS)) == 1
    terms = root.findall(".//lido:termMaterialsTech", NS)
    assert [t.attrib[f"{L}type"][-9:] for t in terms] == ["lido00132", "lido00131"]
    assert terms[0].findtext("lido:conceptID", namespaces=NS) == "http://vocab.getty.edu/aat/300014224"


def test_vocab_term_with_aat_uri_keeps_german_label_without_lang() -> None:
    cms = _minimal([MappingSpec(source_kind=SourceKind.FIELD, source_config={"field_name": "s"},
                                target_key="lido:objectRelationWrap/lido:subjectWrap/lido:subjectSet/lido:subject/lido:subjectConcept/lido:term")])
    root = ET.fromstring(_render(_ctx(fields={"s": {"id": "t", "label": "Fluss", "uri": "http://vocab.getty.edu/aat/300008707"}}), cms))
    term = root.find(".//lido:subjectConcept/lido:term", NS)
    assert term.text == "Fluss"
    assert "{http://www.w3.org/XML/1998/namespace}lang" not in term.attrib
    assert root.find(".//lido:subjectConcept/lido:conceptID", NS).attrib[f"{L}source"] == "AAT"


# ---------------------------------------------------------------------------
# Resources and configurable rights checks
# ---------------------------------------------------------------------------


def _media(**kwargs: Any) -> ExportMediaItem:
    base = {"id": "m1", "filename": "a.jpg", "mime_type": "image/jpeg", "url": "https://x/dl/m1"}
    return ExportMediaItem(**{**base, **kwargs})


CC0 = "https://creativecommons.org/publicdomain/zero/1.0/"


def test_required_media_license_rejects_media_without_license() -> None:
    cms = _minimal(config={"require_media_license": True, "institution_name": "M"})
    errors = LidoFormat().required_field_errors(_ctx(media=[_media()]), cms)
    assert errors == ["Rechteangabe zum Digitalisat fehlt (a.jpg)"]


def test_no_rights_checks_without_configuration() -> None:
    assert LidoFormat().required_field_errors(_ctx(media=[_media()]), _minimal()) == []


def test_allowed_license_list_rejects_other_licenses() -> None:
    cms = _minimal(config={"allowed_license_uris": [CC0]})
    errors = LidoFormat().required_field_errors(_ctx(media=[_media(license_uri="https://example.org/lizenz")]), cms)
    assert errors == ["Lizenz-URI nicht in der erlaubten Liste: https://example.org/lizenz (a.jpg)"]
    # Without require_media_license a medium without license is not an error.
    assert LidoFormat().required_field_errors(_ctx(media=[_media()]), cms) == []


def test_allowed_license_list_checks_record_rights_and_accepts_lines() -> None:
    cms = _minimal(config={"allowed_license_uris": f"{CC0}\n", "record_rights": ";CC0 1.0;9494"})
    errors = LidoFormat().required_field_errors(_ctx(), cms)
    assert errors == ["Rechteangabe der Metadaten (recordRights) nicht in der erlaubten Liste: ;CC0 1.0;9494"]


def test_allowed_list_spelling_is_used_in_the_output() -> None:
    cms = _minimal(config={"resource_sets": True, "allowed_license_uris": [CC0]})
    ctx = _ctx(media=[_media(license_uri="http://creativecommons.org/publicdomain/zero/1.0")])
    assert LidoFormat().required_field_errors(ctx, cms) == []
    root = ET.fromstring(_render(ctx, cms))
    assert root.findtext(".//lido:rightsResource/lido:rightsType/lido:conceptID", namespaces=NS) == CC0


def test_resource_rights_fallback_from_object_field() -> None:
    cms = _minimal(config={"require_media_license": True, "resource_sets": True,
                           "resource_rights_fallback": "object_field:rights.rechtemodell"})
    ctx = _ctx(media=[_media()], fields={"rights": [{"rechtemodell": {"id": "t", "label": "InC",
                                                                       "uri": "http://rightsstatements.org/vocab/InC/1.0/"}}]})
    assert LidoFormat().required_field_errors(ctx, cms) == []
    root = ET.fromstring(_render(ctx, cms))
    assert root.findtext(".//lido:rightsResource/lido:rightsType/lido:conceptID", namespaces=NS) == (
        "http://rightsstatements.org/vocab/InC/1.0/"
    )


def test_resource_set_without_iiif_uses_download_and_real_mime_type() -> None:
    cms = _minimal(config={"resource_sets": True, "institution_name": "Museum", "isil": "DE-1"})
    xml = _render(_ctx(media=[_media(mime_type="application/pdf", license_uri="https://creativecommons.org/publicdomain/zero/1.0/")]), cms)
    assert validate_lido_xml(xml) == []
    root = ET.fromstring(xml)
    link = root.find(".//lido:resourceRepresentation/lido:linkResource", NS)
    assert link.text == "https://x/dl/m1"
    assert link.attrib[f"{L}formatResource"] == "application/pdf"
    assert root.find(".//lido:resourceType", NS) is None
    # No medium rights holder -> institution.
    assert root.findtext(".//lido:rightsResource/lido:rightsHolder/lido:legalBodyName/lido:appellationValue",
                         namespaces=NS) == "Museum"


def test_primary_medium_comes_first() -> None:
    cms = _minimal(config={"resource_sets": True})
    ctx = _ctx(media=[_media(id="m1"), _media(id="m2", is_primary=True)])
    ids = [e.text for e in ET.fromstring(_render(ctx, cms)).iterfind(".//lido:resourceID", NS)]
    assert ids == ["m2", "m1"]


# ---------------------------------------------------------------------------
# OAI-PMH
# ---------------------------------------------------------------------------


def _domain() -> str:
    from katalon.config import settings

    return settings.oai_repository_domain


def test_oai_reports_records_failing_rights_checks_as_deleted(
    ddb_context: ExportRecordContext, ddb_mapping: CompiledMappingSet
) -> None:
    from katalon.services import oaipmh_service

    def hit(ctx: ExportRecordContext) -> dict[str, Any]:
        return {"_id": ctx.record.id, "_source": {"record_type": "object", "export_context": ctx.to_dict()},
                "sort": [ctx.record.id]}

    broken = ddb_context.model_copy(deep=True)
    broken.record.id = "broken"
    broken.media[0].license_uri = None
    broken.fields.pop("rights")  # no fallback license either
    hits = [hit(ddb_context), hit(broken)]
    index = {"object": ddb_mapping}
    common = {"total": 2, "offset": 0, "set_spec": None, "from_": None, "until": None,
              "prefix": "lido", "base_url": "http://test/oai"}

    records = oaipmh_service.list_records(hits, metadata_format=LidoFormat(), mapping_index=index, **common)
    identifiers = oaipmh_service.list_identifiers(hits, metadata_format=LidoFormat(), mapping_index=index, **common)
    for xml in (records, identifiers):
        root = ET.fromstring(xml)
        oai = "{http://www.openarchives.org/OAI/2.0/}"
        headers = {h.findtext(f"{oai}identifier"): h.get("status") for h in root.iter(f"{oai}header")}
        assert headers[f"oai:{_domain()}:object:{ddb_context.record.id}"] is None
        # Not disseminable in this format -> deleted header, no metadata.
        assert headers[f"oai:{_domain()}:object:broken"] == "deleted"
    assert records.count("<lido:lidoWrap") == 1
    # datestamp = the record's own updated_at
    assert "<datestamp>2026-10-02T14:31:07Z</datestamp>" in records


# ---------------------------------------------------------------------------
# Export report
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_report_counts_problems_per_kind(
    monkeypatch: pytest.MonkeyPatch, ddb_context: ExportRecordContext
) -> None:
    from katalon.services import (
        export_context_service,
        export_report_service,
        metadata_format_service,
    )

    good = ddb_context
    bad = ddb_context.model_copy(deep=True)
    bad.record.id, bad.record.idno = "2", "os_ub_2"
    bad.media[0].license_uri = None
    bad.fields.pop("rights")
    contexts = {uuid.UUID(int=1): good, uuid.UUID(int=2): bad}

    yaml_set = yaml.safe_load((FIXTURES / "lido_ddb_mapping.yaml").read_text(encoding="utf-8"))
    mapping_set = ExportMappingSet(id=uuid.uuid4(), format_key="lido", record_type="object",
                                   institution_config=yaml_set["institution_config"], target_subtype=None)
    mapping_set.rules = []

    async def ids(_db: Any, _type: str) -> Any:
        for key in contexts:
            yield key

    monkeypatch.setattr(export_report_service, "get_mapping_set", AsyncMock(return_value=mapping_set))
    monkeypatch.setattr(metadata_format_service, "get_format", AsyncMock(return_value=LidoFormat()))
    monkeypatch.setattr(export_report_service, "_public_record_ids", ids)
    monkeypatch.setattr(export_context_service, "collect_via_relation_types", AsyncMock(return_value=set()))
    monkeypatch.setattr(export_context_service, "build_export_context_from_db",
                        AsyncMock(side_effect=lambda _db, _t, rid, **_kw: contexts[rid]))

    report = await export_report_service.build_report(MagicMock(), mapping_set.id)
    assert report.checked == 2
    by_id = {p.rec_id: p.messages for p in report.problems}
    # No rules in this set: title and work type are missing for both records.
    assert "Rechteangabe zum Digitalisat fehlt (os_ub_0031153_v.jpg)" in by_id["DE-3066--os_ub_2"]
    assert "Rechteangabe zum Digitalisat fehlt (os_ub_0031153_v.jpg)" not in by_id["DE-3066--os_ub_0031153"]
    assert report.counts()["Rechteangabe zum Digitalisat fehlt"] == 1
    assert report.counts()["Objekttitel (appellationValue) ist leer"] == 2


def test_subtype_display_url_becomes_linked_data_uri() -> None:
    ctx = ExportRecordContext(record=ExportRecordSummary(
        id="x", record_type="object", title="T", target_subtype="karte",
        subtype_concept_source="wikidata", subtype_concept_id="Q192425",
        subtype_concept_uri="https://www.wikidata.org/wiki/Q192425", subtype_concept_label="Postkarte",
    ))
    cms = CompiledMappingSet(format_key="lido", record_type="object", rules=[
        MappingSpec(source_kind=SourceKind.RECORD, source_config={"property": "title"},
                    target_key="lido:objectIdentificationWrap/lido:titleWrap/lido:titleSet/lido:appellationValue"),
        MappingSpec(source_kind=SourceKind.RECORD, source_config={"property": "target_subtype"},
                    target_key="lido:objectClassificationWrap/lido:objectWorkTypeWrap/lido:objectWorkType"),
    ])
    root = ET.fromstring(_render(ctx, cms))
    assert root.findtext(".//lido:objectWorkType/lido:conceptID", namespaces=NS) == "http://www.wikidata.org/entity/Q192425"
