# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any

from katalon.integrations.authority_uris import (
    authority_uri,
    normalize_source,
    parse_authority_url,
    source_label,
)
from katalon.integrations.licenses import (
    is_allowed_license,
    license_label,
    license_source,
    normalize_license_uri,
)
from katalon.integrations.metadata_format import (
    HTML_TAG_RE,
    CompiledMappingSet,
    ExportMediaItem,
    ExportRecordContext,
    ExportRelation,
    MappingSpec,
    SourceKind,
)
from katalon.services.metadata_mapping_service import extract_values

LIDO_NS = "http://www.lido-schema.org"
GML_NS = "http://www.opengis.net/gml"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
SCHEMA_LOC = "http://www.lido-schema.org http://www.lido-schema.org/schema/v1.0/lido-v1.0.xsd"

# Only LIDO 1.0 is rendered today. The mapping set's institution_config may carry
# "lido_version" so 1.1-only structures (e.g. objectMaterialsTechWrap) can be
# switched on later without a new config key.
SUPPORTED_LIDO_VERSIONS = ("1.0",)

_T = "http://terminology.lido-schema.org/"
LIDO_TERMS: dict[str, str] = {
    "preferred": _T + "lido00169",
    "alternative": _T + "lido00170",
    "current": _T + "lido00475",
    "uri": _T + "lido00099",
    "local_id": _T + "lido00100",
    "collection": _T + "lido01135",
    "material": _T + "lido00132",
    "technique": _T + "lido00131",
    "person": _T + "lido00163",
    "corporation": _T + "lido00164",
    "production": _T + "lido00007",
    "single_object": _T + "lido00141",
    "record_created": _T + "lido00470",
    "record_modified": _T + "lido00471",
    "representation_master": _T + "lido00464",
    "representation_preview": _T + "lido00465",
}
LIDO_TERMINOLOGY_SOURCE = "LIDO-Terminologie"
DEFAULT_RECORD_RIGHTS = "https://creativecommons.org/publicdomain/zero/1.0/"

TITLE_TARGET = "lido:objectIdentificationWrap/lido:titleWrap/lido:titleSet/lido:appellationValue"
WORK_TYPE_TARGET = "lido:objectClassificationWrap/lido:objectWorkTypeWrap/lido:objectWorkType"
CLASSIFICATION_TARGET = "lido:objectClassificationWrap/lido:classificationWrap/lido:classification"
INSCRIPTION_TARGET = (
    "lido:objectIdentificationWrap/lido:inscriptionsWrap/lido:inscriptions/lido:inscriptionTranscription"
)
DESCRIPTION_TARGET = (
    "lido:objectIdentificationWrap/lido:objectDescriptionWrap/lido:objectDescriptionSet/lido:descriptiveNoteValue"
)
MEASUREMENTS_DISPLAY_TARGET = (
    "lido:objectIdentificationWrap/lido:objectMeasurementsWrap/lido:objectMeasurementsSet/lido:displayObjectMeasurements"
)
MEASUREMENTS_SET_TARGET = (
    "lido:objectIdentificationWrap/lido:objectMeasurementsWrap/lido:objectMeasurementsSet/"
    "lido:objectMeasurements/lido:measurementsSet"
)
RELATED_WORK_TARGET = (
    "lido:objectRelationWrap/lido:relatedWorksWrap/lido:relatedWorkSet/lido:relatedWork/lido:displayObject"
)
SUBJECT_TARGET = (
    "lido:objectRelationWrap/lido:subjectWrap/lido:subjectSet/lido:subject/lido:subjectConcept/lido:term"
)
RIGHTS_WORK_TARGET = "lido:rightsWorkWrap/lido:rightsWorkSet/lido:rightsType/lido:term"
RIGHTS_WORK_CREDIT_TARGET = "lido:rightsWorkWrap/lido:rightsWorkSet/lido:creditLine"
RECORD_RIGHTS_CREDIT_TARGET = "lido:recordWrap/lido:recordRights/lido:creditLine"
RESOURCE_LINK_TARGET = (
    "lido:administrativeMetadata/lido:resourceWrap/lido:resourceSet/lido:resourceRepresentation/lido:linkResource"
)

# Old fixed sub-targets of objectDescriptionSet, kept as aliases of settings.type.
DESCRIPTION_ALIASES = {DESCRIPTION_TARGET + "/short": "brief", DESCRIPTION_TARGET + "/condition": "condition"}

_LEGACY_EVENT_TARGETS = {
    "type": "lido:eventWrap/lido:eventSet/lido:event/lido:eventType/lido:term",
    "actor": (
        "lido:eventWrap/lido:eventSet/lido:event/lido:eventActor/lido:actorInRole/"
        "lido:actor/lido:nameActorSet/lido:appellationValue"
    ),
    "date": "lido:eventWrap/lido:eventSet/lido:event/lido:eventDate/lido:displayDate",
    "earliest_date": "lido:eventWrap/lido:eventSet/lido:event/lido:eventDate/lido:date/lido:earliestDate",
    "place": "lido:eventWrap/lido:eventSet/lido:event/lido:eventPlace/lido:displayPlace",
    "materials_tech": (
        "lido:eventWrap/lido:eventSet/lido:event/lido:eventMaterialsTech/lido:displayMaterialsTech"
    ),
}
EVENT_SUBTARGETS = (*_LEGACY_EVENT_TARGETS, "materials_tech_term", "description")

# Getty vocabularies label in English; tag their terms when the value carries no language.
_ENGLISH_SOURCES = {"aat", "tgn", "ulan"}

# Elements that the XSD requires even without content.
_KEEP_EMPTY = {f"{{{LIDO_NS}}}recordSource", "lido:recordSource"}


# ---------------------------------------------------------------------------
# Text and value helpers
# ---------------------------------------------------------------------------


def _clean_text(val: Any) -> str:
    """Plain, trimmed text: tags become spaces, entities are decoded, NBSP/newlines collapse."""
    if val is None:
        return ""
    if isinstance(val, dict | list) and (val := _display_value(val)) is None:
        return ""
    text = html.unescape(str(val))
    text = HTML_TAG_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def _display_value(val: Any) -> Any:
    """Pull a human-readable scalar out of vocabulary, authority, translatable and group values."""
    if isinstance(val, dict):
        for key in ("label", "value", "term", "name", "title"):
            if key in val and val[key] not in (None, ""):
                return _display_value(val[key])
        if "de" in val or "en" in val:
            return val.get("de") or val.get("en")
        if val.get("uri"):
            return val["uri"]
        for value in val.values():
            if (extracted := _display_value(value)) is not None:
                return extracted
        return None
    if isinstance(val, list):
        return next((extracted for item in val if (extracted := _display_value(item)) is not None), None)
    return val


@dataclass
class _Item:
    """One mapped value with what LIDO can say about it beyond the text."""

    text: str
    uri: str | None = None
    source: str | None = None  # normalized authority source key (gnd, aat, ...)
    lang: str | None = None
    relation: ExportRelation | None = None
    extra_uris: list[str] = field(default_factory=list)


_KNOWN_VALUE_KEYS = {"label", "value", "term", "name", "title", "idno", "id", "uri", "de", "en", "external_id"}


def _item_from_value(value: Any) -> _Item | None:
    if value is None or value == "":
        return None
    if not isinstance(value, dict):
        text = _clean_text(value)
        if not text:
            return None
        parsed = parse_authority_url(text) if text.startswith("http") else None
        return _Item(text=text, uri=parsed[1] if parsed else None, source=parsed[0] if parsed else None)
    if not (_KNOWN_VALUE_KEYS & value.keys()):
        # Entry of a group field mapped as a whole: use its first sub-value.
        return next(
            (item for sub in value.values() if (item := _item_from_value(sub)) is not None), None
        )
    lang = value.get("lang") if isinstance(value.get("lang"), str) else None
    label = value.get("label")
    if isinstance(label, dict):
        text = _clean_text(label.get("de") or label.get("en") or _display_value(label))
        if not label.get("de") and label.get("en"):
            lang = lang or "en"
    else:
        text = _clean_text(value)
    source = normalize_source(value.get("source")) or None
    if source in _ENGLISH_SOURCES and not lang:
        # Authority values picked from Getty carry the English preferred label.
        lang = "en"
    uri = _clean_text(value.get("uri")) or authority_uri(source, value.get("external_id"))
    if uri and not source and (parsed := parse_authority_url(uri)):
        source = parsed[0]
    if not uri:
        # URL fields ({value: "http://d-nb.info/gnd/...", label: "GND"}) and pasted links.
        for candidate in (value.get("value"), text):
            if isinstance(candidate, str) and (parsed := parse_authority_url(candidate)):
                source, uri = parsed
                break
    extra = [str(u) for u in value.get("exact_match_uris") or [] if u]
    if not text and not uri:
        return None
    return _Item(text=text or (uri or ""), uri=uri or None, source=source, lang=lang, extra_uris=extra)


def _field_leaves(ctx: ExportRecordContext, field_name: str) -> list[Any]:
    """Raw leaf values of a field; ``group.child`` addresses a sub-field of a group."""
    if "." in field_name:
        group, child = field_name.split(".", 1)
        leaves: list[Any] = []
        entries = ctx.fields.get(group)
        for entry in entries if isinstance(entries, list) else [entries]:
            if isinstance(entry, dict) and child in entry:
                value = entry[child]
                leaves.extend(value if isinstance(value, list) else [value])
        return leaves
    raw = ctx.fields.get(field_name)
    if raw is None:
        return [str(v) for v in extract_values(ctx, field_name)]
    return raw if isinstance(raw, list) else [raw]


def _matching_relations(ctx: ExportRecordContext, config: dict[str, Any]) -> list[ExportRelation]:
    relation_type = config.get("relation_type")
    target_type = config.get("target_type")
    direction = str(config.get("direction") or "outbound")
    return [
        rel
        for rel in ctx.relations
        if rel.direction == direction
        and (not relation_type or rel.relation_type == relation_type)
        and (not target_type or rel.target_type == target_type)
    ]


def _relation_items(ctx: ExportRecordContext, rule: MappingSpec) -> list[_Item]:
    config = rule.source_config
    relations = _matching_relations(ctx, config)
    via = config.get("via")
    if isinstance(via, dict) and via.get("relation_type"):
        via_cfg = {"direction": "outbound", **via}
        relations = [
            second
            for rel in relations
            for second in _matching_relations(
                ExportRecordContext(record=ctx.record, relations=rel.target_relations), via_cfg
            )
        ]
    target_field = config.get("target_field")
    items: list[_Item] = []
    for rel in relations:
        raw = rel.target_values.get(target_field) if target_field else (rel.target_label or rel.target_idno)
        item = _item_from_value(raw)
        if item is not None:
            item.relation = rel
            items.append(item)
    return items


def _rule_items(ctx: ExportRecordContext, rule: MappingSpec) -> list[_Item]:
    items: list[_Item | None] = []
    if rule.source_kind == SourceKind.FIELD and rule.field_name:
        items = [_item_from_value(v) for v in _field_leaves(ctx, rule.field_name)]
    elif rule.source_kind == SourceKind.RELATION:
        items = list(_relation_items(ctx, rule))
    elif rule.source_kind == SourceKind.RECORD:
        property_name = rule.source_config.get("property")
        if property_name and (value := getattr(ctx.record, property_name, None)):
            items = [_item_from_value(value)]
    elif rule.source_kind == SourceKind.CONSTANT:
        items = [_item_from_value(rule.source_config.get("value") or rule.settings.get("value"))]
    elif rule.source_kind == SourceKind.MEDIA:
        property_name = rule.source_config.get("property", "url")
        items = [
            _item_from_value(getattr(media, property_name, None))
            for media in ctx.media
            if media.is_public
        ]
    prefix = str(rule.settings.get("prefix") or "")
    result = [item for item in items if item is not None and item.text]
    if prefix:
        for item in result:
            item.text = f"{prefix}{item.text}"
    return result


def _rule_values(ctx: ExportRecordContext, rule: MappingSpec) -> list[str]:
    return [item.text for item in _rule_items(ctx, rule)]


def _sub(parent: ET.Element, tag: str, text: Any = None, **attrs: Any) -> ET.Element:
    """SubElement with trimmed text; empty attribute values are left out."""
    clean_attrs = {
        key.replace("__", ":"): cleaned
        for key, value in attrs.items()
        if (cleaned := _clean_text(value))
    }
    el = ET.SubElement(parent, tag, clean_attrs)
    if text is not None:
        el.text = _clean_text(text) or None
    return el


def _concept_id(parent: ET.Element, uri: str | None, source: str | None, pref: str | None = None) -> None:
    if uri:
        _sub(
            parent,
            "lido:conceptID",
            uri,
            lido__pref=pref,
            lido__type=LIDO_TERMS["uri"],
            lido__source=source_label(source) if source else None,
        )


def _item_lang(item: _Item, rule: MappingSpec) -> str | None:
    return rule.settings.get("lang") or item.lang


# ---------------------------------------------------------------------------
# Dates and measurements
# ---------------------------------------------------------------------------

_DATE_PART = re.compile(r"^(-?\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$")


def _strip_qualifier(value: str) -> str:
    return value.removesuffix("~?").removesuffix("~").removesuffix("?")


def date_limits(value: str) -> tuple[str | None, str | None] | None:
    """ISO bounds of an EDTF-lite date ("1905", "1905/", "1900-03/1901"), keeping precision.

    Returns None for values that are not EDTF-lite (free text such as "um 1900").
    """
    from katalon.services.search_service import date_bounds  # validation shared with the index

    raw = (value or "").strip()
    try:
        date_bounds(raw)
    except ValueError:
        return None
    if "/" in raw:
        start, end = raw.split("/", 1)
        return (_strip_qualifier(start) or None, _strip_qualifier(end) or None)
    single = _strip_qualifier(raw)
    return (single, single) if _DATE_PART.match(single) else None


def _format_qualified(value: str) -> str:
    def bce(date: str) -> str:
        match = re.match(r"^-(\d{4})(.*)$", date)
        return f"{int(match.group(1)) + 1}{match.group(2)} v. Chr." if match else date

    for suffix, template in (("~?", "ca. {} (unsicher)"), ("~", "ca. {}"), ("?", "{} (unsicher)")):
        if value.endswith(suffix):
            return template.format(bce(value[: -len(suffix)]))
    return bce(value)


def format_date_display(value: str) -> str:
    """German display text of an EDTF-lite value (same wording as the portal)."""
    if "/" in value:
        start, end = value.split("/", 1)
        if not start:
            return f"vor {_format_qualified(end)}"
        if not end:
            return f"nach {_format_qualified(start)}"
        return f"{_format_qualified(start)}–{_format_qualified(end)}"
    return _format_qualified(value)


_MEASUREMENT = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*([^\d\s.,][^\d]*)?\s*$")


def parse_measurement(value: str, default_unit: str | None = None) -> tuple[str, str, str] | None:
    """'9,2 cm' -> ('9,2', '9.2', 'cm'); None if no number/unit can be read."""
    match = _MEASUREMENT.match(value or "")
    if not match:
        return None
    unit = (match.group(2) or "").strip() or (default_unit or "").strip()
    if not unit:
        return None
    return match.group(1), match.group(1).replace(",", "."), unit


# ---------------------------------------------------------------------------
# Legal bodies, rights and media
# ---------------------------------------------------------------------------


def _institution(config: dict[str, Any]) -> dict[str, str]:
    def value(key: str, legacy: str | None = None) -> str:
        return _clean_text(config.get(key) or (config.get(legacy) if legacy else None))

    return {
        "isil": value("isil"),
        "name": value("institution_name", "repository_name"),
        "website": value("website", "repository_url"),
        "location": value("location", "repository_location"),
    }


def _legal_body(
    parent: ET.Element,
    tag: str,
    *,
    isil: str = "",
    name: str = "",
    website: str = "",
    uri: str | None = None,
) -> ET.Element:
    body = _sub(parent, tag)
    if isil:
        _sub(
            body,
            "lido:legalBodyID",
            f"https://sigel.staatsbibliothek-berlin.de/suche?isil={isil}",
            lido__type=LIDO_TERMS["local_id"],
            lido__source="ISIL",
        )
    elif uri:
        _sub(body, "lido:legalBodyID", uri, lido__type=LIDO_TERMS["uri"])
    if name:
        _sub(_sub(body, "lido:legalBodyName"), "lido:appellationValue", name)
    if website:
        _sub(body, "lido:legalBodyWeblink", website)
    return body


def _rights_type(parent: ET.Element, uri: str | None, term: str | None) -> None:
    rights_type = _sub(parent, "lido:rightsType")
    if uri:
        _sub(
            rights_type,
            "lido:conceptID",
            uri,
            lido__type=LIDO_TERMS["uri"],
            lido__source=license_source(uri),
        )
    if term:
        _sub(rights_type, "lido:term", term)


def resource_sets_enabled(config: dict[str, Any]) -> bool:
    return bool(config.get("resource_sets"))


def allowed_licenses(config: dict[str, Any]) -> list[str]:
    """``allowed_license_uris`` as a list (empty = no restriction)."""
    raw = config.get("allowed_license_uris") or []
    entries = raw.splitlines() if isinstance(raw, str) else raw
    return [str(e).strip() for e in entries if str(e).strip()]


def _license(uri: Any, config: dict[str, Any]) -> str | None:
    return normalize_license_uri(_clean_text(uri) or None, allowed_licenses(config))


def media_license(ctx: ExportRecordContext, media: ExportMediaItem, config: dict[str, Any]) -> str | None:
    """License URI of a medium, with the configured fallback for media without one."""
    if media.license_uri:
        return _license(media.license_uri, config)
    fallback = str(config.get("resource_rights_fallback") or "none")
    if fallback.startswith("object_field:"):
        field_name = fallback.split(":", 1)[1].strip()
        for leaf in _field_leaves(ctx, field_name):
            item = _item_from_value(leaf)
            candidate = (item.uri if item else None) or (item.text if item else "")
            if candidate and candidate.startswith("http"):
                return _license(candidate, config)
        return None
    if fallback == "default":
        return _license(config.get("resource_rights_default_uri"), config)
    return None


def record_rights_uri(config: dict[str, Any]) -> str:
    return _license(config.get("record_rights"), config) or DEFAULT_RECORD_RIGHTS


def _public_media(ctx: ExportRecordContext) -> list[ExportMediaItem]:
    media = [m for m in ctx.media if m.is_public]
    return sorted(media, key=lambda m: not m.is_primary)


def _resource_set(
    wrap: ET.Element,
    ctx: ExportRecordContext,
    media: ExportMediaItem,
    config: dict[str, Any],
    institution: dict[str, str],
) -> None:
    resource_set = _sub(wrap, "lido:resourceSet")
    resource_id = media.filename if config.get("resource_id") == "filename" else media.id
    _sub(resource_set, "lido:resourceID", resource_id, lido__type=LIDO_TERMS["local_id"])
    master = _sub(resource_set, "lido:resourceRepresentation", lido__type=LIDO_TERMS["representation_master"])
    if media.iiif_base:
        # IIIF default.jpg is always delivered as JPEG, whatever the master format.
        _sub(master, "lido:linkResource", f"{media.iiif_base}/full/max/0/default.jpg",
             lido__formatResource="image/jpeg")
        if config.get("resource_preview", True):
            preview = _sub(resource_set, "lido:resourceRepresentation",
                           lido__type=LIDO_TERMS["representation_preview"])
            _sub(preview, "lido:linkResource", f"{media.iiif_base}/full/!400,400/0/default.jpg",
                 lido__formatResource="image/jpeg")
        if config.get("resource_iiif_manifest") and media.iiif_manifest_url:
            manifest = _sub(resource_set, "lido:resourceRepresentation")
            _sub(manifest, "lido:linkResource", media.iiif_manifest_url,
                 lido__formatResource="application/ld+json")
    else:
        _sub(master, "lido:linkResource", media.url, lido__formatResource=media.mime_type)
    resource_type = config.get("resource_type") or (
        "image" if media.mime_type.startswith("image/") else None
    )
    if resource_type:
        _sub(_sub(resource_set, "lido:resourceType"), "lido:term", resource_type)

    license_uri = media_license(ctx, media, config)
    rights = _sub(resource_set, "lido:rightsResource")
    _rights_type(rights, license_uri, license_label(license_uri) or media.rights_statement_label)
    if media.rights_holder:
        _legal_body(rights, "lido:rightsHolder", name=media.rights_holder, uri=media.rights_holder_uri)
    elif institution["name"]:
        _legal_body(rights, "lido:rightsHolder", isil=institution["isil"], name=institution["name"])
    if media.credit_line:
        _sub(rights, "lido:creditLine", media.credit_line)


# ---------------------------------------------------------------------------
# Work types
# ---------------------------------------------------------------------------


def _get_work_type_concepts(ctx: ExportRecordContext, mapping_set: CompiledMappingSet) -> list[dict[str, Any]]:
    """objectWorkType entries: {"type", "concepts": [(uri, source, pref)], "terms": [(text, lang, pref)]}."""
    rules = [r for r in mapping_set.rules if r.target_key == WORK_TYPE_TARGET and r.is_enabled]
    rec = ctx.record
    results: list[dict[str, Any]] = []

    def subtype_uri() -> str | None:
        # Source + ID first: the admin stores display URLs (e.g. wikidata.org/wiki/…) in
        # concept_uri, while LIDO needs the Linked-Data form.
        stored = rec.subtype_concept_uri
        parsed = parse_authority_url(stored) if stored else None
        return (
            authority_uri(rec.subtype_concept_source, rec.subtype_concept_id)
            or (parsed[1] if parsed else None)
            or stored
            or rec.subtype_concept_id
        )

    def entry(type_: Any, uri: str | None, source: str | None, term: str, lang: str | None = None) -> dict[str, Any]:
        return {
            "type": type_,
            "concepts": [(uri, source, None)] if uri else [],
            "terms": [(term, lang, None)] if term else [],
        }

    for rule in rules:
        type_ = rule.settings.get("type")
        if rule.source_kind == SourceKind.FIELD and rule.field_name:
            for leaf in _field_leaves(ctx, rule.field_name):
                if isinstance(leaf, dict):
                    item = _item_from_value(leaf)
                    concept = leaf.get("concept_uri") or (item.uri if item else None) or leaf.get("concept_id")
                    source = normalize_source(leaf.get("authority_source")) if leaf.get("authority_source") else (item.source if item else None)
                    term = _clean_text(leaf.get("term")) or (item.text if item else "")
                    if concept or term:
                        results.append(entry(type_, concept, source, term, item.lang if item else None))
                elif (term := _clean_text(leaf)) and type_:
                    results.append(entry(type_, None, None, term))
                elif term:
                    results.append(entry(None, subtype_uri(), rec.subtype_concept_source, term))
        elif rule.source_kind == SourceKind.RECORD and (rec.subtype_concept_id or rec.subtype_concept_uri):
            term = rec.subtype_concept_label or str(
                getattr(rec, rule.source_config.get("property", "target_subtype"), None)
                or rec.target_subtype
                or ""
            )
            alternatives = [alt for alt in rec.subtype_concept_alternatives if isinstance(alt, dict)]
            if not alternatives:
                results.append(entry(type_, subtype_uri(), rec.subtype_concept_source, term, rule.settings.get("lang")))
                continue
            pref, alt_pref = LIDO_TERMS["preferred"], LIDO_TERMS["alternative"]
            concepts = [(subtype_uri(), rec.subtype_concept_source, pref)]
            terms = [(term, rule.settings.get("lang") or "de", pref)]
            for alt in alternatives:
                alt_uri = _clean_text(alt.get("uri")) or authority_uri(alt.get("source"), alt.get("id"))
                if alt_uri:
                    concepts.append((alt_uri, normalize_source(alt.get("source")) or None, alt_pref))
                if label := _clean_text(alt.get("label")):
                    terms.append((label, _clean_text(alt.get("lang")) or None, alt_pref))
            results.append({"type": type_, "concepts": concepts, "terms": terms})
        elif rule.source_kind == SourceKind.CONSTANT:
            if const_val := _clean_text(rule.source_config.get("value") or rule.settings.get("value")):
                results.append(entry(type_, None, None, const_val))

    if not results and not any(rule.source_kind == SourceKind.RECORD for rule in rules):
        extracted = [value for rule in rules for value in _rule_values(ctx, rule)]
        for val in extracted or [rec.subtype_concept_label or rec.target_subtype or ""]:
            results.append(entry(None, subtype_uri(), rec.subtype_concept_source, val))

    return results


# ---------------------------------------------------------------------------
# Record-level checks
# ---------------------------------------------------------------------------


def missing_required_fields(ctx: ExportRecordContext, mapping_set: CompiledMappingSet) -> list[str]:
    """Check this record's actual data for LIDO's required fields and configured rights checks.

    A mapping can be configured correctly (checked by `validate_mapping`) and still
    resolve empty for a given record, e.g. an object whose "label" field is blank.
    """
    rules_by_target = mapping_set.by_target()
    config = mapping_set.institution_config or {}
    errors: list[str] = []

    title_values = [v for rule in rules_by_target.get(TITLE_TARGET, []) for v in _rule_values(ctx, rule)]
    if not title_values:
        errors.append("Objekttitel (appellationValue) ist leer")

    work_types = _get_work_type_concepts(ctx, mapping_set)
    if not any(term for wt in work_types for term, _lang, _pref in wt["terms"]):
        errors.append("Objektart / Typ (objectWorkType) ist leer")

    errors.extend(rights_check_errors(ctx, config))
    return errors


def rights_check_errors(ctx: ExportRecordContext, config: dict[str, Any]) -> list[str]:
    """Rights checks switched on per mapping set (``require_media_license``,
    ``allowed_license_uris``); a recipient's requirements live in its configuration."""
    errors: list[str] = []
    allowed = allowed_licenses(config)
    if allowed and not is_allowed_license(record_rights := record_rights_uri(config), allowed):
        errors.append(f"Rechteangabe der Metadaten (recordRights) nicht in der erlaubten Liste: {record_rights}")
    require = bool(config.get("require_media_license"))
    if not require and not allowed:
        return errors
    for media in _public_media(ctx):
        license_uri = media_license(ctx, media, config)
        if not license_uri:
            if require:
                errors.append(f"Rechteangabe zum Digitalisat fehlt ({media.filename})")
        elif allowed and not is_allowed_license(license_uri, allowed):
            errors.append(f"Lizenz-URI nicht in der erlaubten Liste: {license_uri} ({media.filename})")
    return errors


# ---------------------------------------------------------------------------
# Post-processing
# ---------------------------------------------------------------------------


def _prune_empty(el: ET.Element) -> bool:
    """Remove empty elements bottom-up; return True if ``el`` itself is empty."""
    for child in list(el):
        if _prune_empty(child) and child.tag not in _KEEP_EMPTY:
            el.remove(child)
    return len(el) == 0 and not (el.text or "").strip()


def _dedupe(el: ET.Element) -> None:
    """Drop repeated siblings that are identical (tag, attributes, text, subtree)."""
    seen: set[bytes] = set()
    for child in list(el):
        _dedupe(child)
        key = ET.tostring(child)
        if key in seen:
            el.remove(child)
        else:
            seen.add(key)


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


def _event_specs(config: dict[str, Any], rules_by_target: dict[str, list[MappingSpec]]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    seen: set[str] = set()
    configured = config.get("lido_events")
    if isinstance(configured, list):
        for ev in configured:
            eid = str((ev or {}).get("id") or "").strip()
            if eid and eid not in seen:
                seen.add(eid)
                specs.append(ev)
    if "production" not in seen:
        seen.add("production")
        specs.insert(0, {"id": "production", "type": "Herstellung", "type_concept_uri": LIDO_TERMS["production"]})
    for target_key in rules_by_target:
        if target_key.startswith("lido:events/"):
            parts = target_key.split("/")
            if len(parts) >= 2 and parts[1] not in seen:
                seen.add(parts[1])
                specs.append({"id": parts[1], "type": parts[1].capitalize()})
    return specs


def _id_fields(rule: MappingSpec, config: dict[str, Any], key: str) -> list[dict[str, Any]]:
    configured = rule.settings.get(key) or config.get(key) or []
    return [entry for entry in configured if isinstance(entry, dict) and entry.get("field")]


def _authority_ids(values: dict[str, Any], id_fields: list[dict[str, Any]]) -> list[tuple[str, str | None]]:
    """(uri, source) pairs from authority/url fields of a related record, deduplicated."""
    result: list[tuple[str, str | None]] = []
    seen: set[str] = set()
    for entry in id_fields:
        raw = values.get(str(entry["field"]))
        for leaf in raw if isinstance(raw, list) else [raw]:
            item = _item_from_value(leaf)
            if item is None:
                continue
            source = item.source or normalize_source(entry.get("source")) or None
            uri = item.uri
            if not uri and item.text:
                parsed = parse_authority_url(item.text)
                uri = parsed[1] if parsed else authority_uri(source, item.text)
            if uri and uri not in seen:
                seen.add(uri)
                result.append((uri, source))
    return result


def _render_actor(event: ET.Element, item: _Item, rule: MappingSpec, config: dict[str, Any]) -> None:
    actor_in_role = _sub(_sub(event, "lido:eventActor"), "lido:actorInRole")
    rel = item.relation
    actor_types = config.get("actor_types") or {}
    kind = actor_types.get(rel.target_subtype) if rel and rel.target_subtype else None
    actor = _sub(actor_in_role, "lido:actor", lido__type=LIDO_TERMS.get(str(kind)) if kind else None)
    ids = _authority_ids(rel.target_values, _id_fields(rule, config, "actor_id_fields")) if rel else []
    if not rel and item.uri:
        ids = [(item.uri, item.source)]
    for uri, source in ids:
        _sub(actor, "lido:actorID", uri, lido__type=LIDO_TERMS["uri"], lido__source=source_label(source))
    _sub(_sub(actor, "lido:nameActorSet"), "lido:appellationValue", item.text, lido__pref=LIDO_TERMS["preferred"])
    role = _clean_text(rule.settings.get("role") or rule.source_config.get("role"))
    role_uri = _clean_text(rule.settings.get("role_uri"))
    if role or role_uri:
        role_actor = _sub(actor_in_role, "lido:roleActor")
        _concept_id(role_actor, role_uri or None, None)
        _sub(role_actor, "lido:term", role)


def _render_place(event: ET.Element, item: _Item, rule: MappingSpec, config: dict[str, Any]) -> None:
    event_place = _sub(event, "lido:eventPlace")
    _sub(event_place, "lido:displayPlace", item.text)
    place = _sub(event_place, "lido:place")
    rel = item.relation
    ids = _authority_ids(rel.target_values, _id_fields(rule, config, "place_id_fields")) if rel else []
    if not rel and item.uri:
        ids = [(item.uri, item.source)]
    for uri, source in ids:
        _sub(place, "lido:placeID", uri, lido__type=LIDO_TERMS["uri"], lido__source=source_label(source))
    _sub(_sub(place, "lido:namePlaceSet"), "lido:appellationValue", item.text)


def _render_event(
    event_wrap: ET.Element,
    ctx: ExportRecordContext,
    spec: dict[str, Any],
    rules: dict[str, list[MappingSpec]],
    config: dict[str, Any],
) -> None:
    def items(sub: str) -> list[tuple[MappingSpec, _Item]]:
        return [(rule, item) for rule in rules.get(sub, []) for item in _rule_items(ctx, rule)]

    types = items("type")
    actors = items("actor")
    dates = items("date")
    earliest = items("earliest_date")
    places = items("place")
    materials = items("materials_tech")
    terms = items("materials_tech_term")
    descriptions = items("description")
    if not any((types, actors, dates, earliest, places, materials, terms, descriptions)):
        return

    event = _sub(_sub(event_wrap, "lido:eventSet"), "lido:event")
    type_name = types[0][1].text if types else _clean_text(spec.get("type")) or "Herstellung"
    type_uri = _clean_text(spec.get("type_concept_uri")) or (
        LIDO_TERMS["production"] if type_name.casefold() == "herstellung" else ""
    )
    event_type = _sub(event, "lido:eventType")
    if type_uri:
        _sub(event_type, "lido:conceptID", type_uri, lido__type=LIDO_TERMS["uri"],
             lido__source=LIDO_TERMINOLOGY_SOURCE)
    _sub(event_type, "lido:term", type_name)

    for rule, item in actors:
        _render_actor(event, item, rule, config)

    if dates or earliest:
        event_date = _sub(event, "lido:eventDate")
        limits: tuple[str | None, str | None] | None = None
        for rule, item in dates:
            parsed = date_limits(item.text)
            label = None
            if label_field := rule.settings.get("label_field"):
                label = next(
                    (i.text for leaf in _field_leaves(ctx, str(label_field)) if (i := _item_from_value(leaf))),
                    None,
                )
            _sub(event_date, "lido:displayDate", format_date_display(item.text) if parsed else item.text,
                 lido__label=label)
            limits = limits or parsed
        date_el = _sub(event_date, "lido:date")
        if earliest:
            for _rule, item in earliest:
                _sub(date_el, "lido:earliestDate", item.text)
        elif limits:
            _sub(date_el, "lido:earliestDate", limits[0])
            _sub(date_el, "lido:latestDate", limits[1])

    for rule, item in places:
        _render_place(event, item, rule, config)

    for _rule, item in materials:
        _sub(_sub(event, "lido:eventMaterialsTech"), "lido:displayMaterialsTech", item.text)
    if terms:
        materials_tech = _sub(_sub(event, "lido:eventMaterialsTech"), "lido:materialsTech")
        for rule, item in terms:
            kind = str(rule.settings.get("kind") or "material")
            term_el = _sub(materials_tech, "lido:termMaterialsTech", lido__type=LIDO_TERMS.get(kind))
            _concept_id(term_el, item.uri, item.source)
            _sub(term_el, "lido:term", item.text, xml__lang=_item_lang(item, rule))

    for _rule, item in descriptions:
        _sub(_sub(event, "lido:eventDescriptionSet"), "lido:descriptiveNoteValue", item.text)


def build_lido_element(
    ctx: ExportRecordContext,
    mapping_set: CompiledMappingSet,
    institution_config: dict[str, Any] | None = None,
    *,
    wrap_envelope: bool = True,
) -> ET.Element:
    """Build a LIDO 1.0 envelope from explicit mappings and institution values."""
    config = institution_config or {}
    rules_by_target = mapping_set.by_target()
    institution = _institution(config)

    def target_items(target_key: str) -> list[tuple[MappingSpec, _Item]]:
        return [(rule, item) for rule in rules_by_target.get(target_key, []) for item in _rule_items(ctx, rule)]

    idno = ctx.record.idno or ctx.record.id
    isil = institution["isil"]

    portal_host = _clean_text(config.get("portal_host")).rstrip("/")
    portal_paths = {
        "object": "objects",
        "entity": "entities",
        "place": "places",
        "occurrence": "occurrences",
        "collection": "collections",
    }
    record_info_link = (
        f"{portal_host}/{portal_paths[ctx.record.record_type]}/{ctx.record.id}"
        if portal_host and ctx.record.record_type in portal_paths
        else ctx.record.canonical_url
    )

    wrap = ET.Element("lido:lidoWrap", {
        "xmlns:lido": LIDO_NS,
        "xmlns:gml": GML_NS,
        "xmlns:xsi": XSI_NS,
        "xsi:schemaLocation": SCHEMA_LOC,
    })
    lido = ET.SubElement(wrap, "lido:lido")
    _sub(lido, "lido:lidoRecID", f"{isil}--{idno}" if isil else idno, lido__type=LIDO_TERMS["local_id"])

    category = _sub(lido, "lido:category")
    _sub(category, "lido:conceptID", "http://www.cidoc-crm.org/cidoc-crm/E22_Human-Made_Object",
         lido__type=LIDO_TERMS["uri"], lido__source="CIDOC CRM")
    _sub(category, "lido:term", "Human-Made Object")

    descriptive = _sub(lido, "lido:descriptiveMetadata", xml__lang="de")

    # --- objectClassificationWrap -------------------------------------------------
    classification = _sub(descriptive, "lido:objectClassificationWrap")
    work_type_wrap = _sub(classification, "lido:objectWorkTypeWrap")
    for wt in _get_work_type_concepts(ctx, mapping_set):
        work_type = _sub(work_type_wrap, "lido:objectWorkType", lido__type=wt["type"])
        for uri, source, pref in wt["concepts"]:
            _concept_id(work_type, uri, source, pref)
        for text, lang, pref in wt["terms"]:
            _sub(work_type, "lido:term", text, lido__pref=pref, xml__lang=lang)

    classification_wrap = _sub(classification, "lido:classificationWrap")
    for rule, item in target_items(CLASSIFICATION_TARGET):
        type_ = rule.settings.get("type")
        cls = _sub(classification_wrap, "lido:classification",
                   lido__type=LIDO_TERMS.get(str(type_), type_) if type_ else None)
        _concept_id(cls, item.uri, item.source)
        _sub(cls, "lido:term", item.text, xml__lang=_item_lang(item, rule))

    # --- objectIdentificationWrap ---------------------------------------------------
    identification = _sub(descriptive, "lido:objectIdentificationWrap")
    title_wrap = _sub(identification, "lido:titleWrap")
    for index, (_rule, item) in enumerate(target_items(TITLE_TARGET)):
        pref = LIDO_TERMS["preferred"] if index == 0 else LIDO_TERMS["alternative"]
        _sub(_sub(title_wrap, "lido:titleSet"), "lido:appellationValue", item.text, lido__pref=pref)

    inscriptions_wrap = _sub(identification, "lido:inscriptionsWrap")
    for rule, item in target_items(INSCRIPTION_TARGET):
        inscription = _sub(inscriptions_wrap, "lido:inscriptions")
        _sub(inscription, "lido:inscriptionTranscription", item.text)
        if description := rule.settings.get("description"):
            _sub(_sub(inscription, "lido:inscriptionDescription"), "lido:descriptiveNoteValue", description)

    if institution["name"]:
        repository_set = _sub(_sub(identification, "lido:repositoryWrap"), "lido:repositorySet",
                              lido__type=LIDO_TERMS["current"])
        _legal_body(repository_set, "lido:repositoryName", isil=isil, name=institution["name"],
                    website=institution["website"])
        _sub(repository_set, "lido:workID", idno, lido__type="Objekt-Signatur")
        for entry in config.get("work_ids") or []:
            if not isinstance(entry, dict) or not entry.get("field_name"):
                continue
            for leaf in _field_leaves(ctx, str(entry["field_name"])):
                if (work_id := _item_from_value(leaf)) is not None:
                    _sub(repository_set, "lido:workID", work_id.text, lido__type=entry.get("type"))
        location = _sub(repository_set, "lido:repositoryLocation")
        for entry in config.get("location_place_ids") or []:
            if isinstance(entry, dict):
                uri = authority_uri(entry.get("source"), str(entry.get("id") or ""))
                _sub(location, "lido:placeID", uri, lido__type=LIDO_TERMS["uri"],
                     lido__source=source_label(entry.get("source")) if uri else None)
        _sub(_sub(location, "lido:namePlaceSet"), "lido:appellationValue", institution["location"])

    description_wrap = _sub(identification, "lido:objectDescriptionWrap")
    for target in (DESCRIPTION_TARGET, *DESCRIPTION_ALIASES):
        for rule, item in target_items(target):
            type_ = rule.settings.get("type") or DESCRIPTION_ALIASES.get(target)
            description_set = _sub(description_wrap, "lido:objectDescriptionSet", lido__type=type_)
            _sub(description_set, "lido:descriptiveNoteValue", item.text)

    measurements_wrap = _sub(identification, "lido:objectMeasurementsWrap")
    display_values = [item.text for _rule, item in target_items(MEASUREMENTS_DISPLAY_TARGET)]
    structured: list[tuple[str, str, str, str]] = []  # (type, shown number, value, unit)
    for rule, item in target_items(MEASUREMENTS_SET_TARGET):
        parsed = parse_measurement(item.text, rule.settings.get("unit"))
        if parsed is None:
            display_values.append(item.text)
            continue
        structured.append((_clean_text(rule.settings.get("measurement_type")), *parsed))
    if not structured:
        for value in display_values:
            _sub(_sub(measurements_wrap, "lido:objectMeasurementsSet"), "lido:displayObjectMeasurements", value)
    else:
        measurements_set = _sub(measurements_wrap, "lido:objectMeasurementsSet")
        units = {unit for _t, _s, _v, unit in structured}
        if not display_values and len(units) == 1:
            display_values = [" × ".join(shown for _t, shown, _v, _u in structured) + f" {units.pop()}"]
        for value in display_values:
            _sub(measurements_set, "lido:displayObjectMeasurements", value)
        object_measurements = _sub(measurements_set, "lido:objectMeasurements")
        for type_, _shown, value, unit in structured:
            ms = _sub(object_measurements, "lido:measurementsSet")
            _sub(ms, "lido:measurementType", type_ or "Maß")
            _sub(ms, "lido:measurementUnit", unit)
            _sub(ms, "lido:measurementValue", value)

    # --- eventWrap --------------------------------------------------------------------
    event_wrap = _sub(descriptive, "lido:eventWrap")
    for spec in _event_specs(config, rules_by_target):
        eid = spec.get("id")
        rules: dict[str, list[MappingSpec]] = {
            sub: list(rules_by_target.get(f"lido:events/{eid}/{sub}", [])) for sub in EVENT_SUBTARGETS
        }
        if eid == "production":
            for sub, legacy in _LEGACY_EVENT_TARGETS.items():
                rules[sub].extend(rules_by_target.get(legacy, []))
        _render_event(event_wrap, ctx, spec, rules, config)

    # --- objectRelationWrap -------------------------------------------------------------
    relation_wrap = _sub(descriptive, "lido:objectRelationWrap")
    subject_wrap = _sub(relation_wrap, "lido:subjectWrap")
    for rule, item in target_items(SUBJECT_TARGET):
        concept = _sub(_sub(_sub(subject_wrap, "lido:subjectSet"), "lido:subject"), "lido:subjectConcept")
        _concept_id(concept, item.uri, item.source)
        _sub(concept, "lido:term", item.text, xml__lang=_item_lang(item, rule))
    related_wrap = _sub(relation_wrap, "lido:relatedWorksWrap")
    for rule, item in target_items(RELATED_WORK_TARGET):
        related_set = _sub(related_wrap, "lido:relatedWorkSet")
        _sub(_sub(related_set, "lido:relatedWork"), "lido:displayObject", item.text)
        rel_type = rule.settings.get("rel_type") or rule.source_config.get("rel_type")
        _sub(_sub(related_set, "lido:relatedWorkRelType"), "lido:term", rel_type)

    # --- administrativeMetadata ---------------------------------------------------------
    administrative = _sub(lido, "lido:administrativeMetadata", xml__lang="de")
    rights_set = _sub(_sub(administrative, "lido:rightsWorkWrap"), "lido:rightsWorkSet")
    for _rule, item in target_items(RIGHTS_WORK_TARGET):
        uri = _license(item.uri, config) if item.uri else None
        _rights_type(rights_set, uri, item.text if item.text != item.uri else license_label(uri) or item.text)
    if config.get("rights_work_holder") and institution["name"]:
        _legal_body(rights_set, "lido:rightsHolder", isil=isil, name=institution["name"],
                    website=institution["website"])
    for _rule, item in target_items(RIGHTS_WORK_CREDIT_TARGET):
        _sub(rights_set, "lido:creditLine", item.text)

    record_wrap = _sub(administrative, "lido:recordWrap")
    _sub(record_wrap, "lido:recordID", idno, lido__type=LIDO_TERMS["local_id"])
    record_type = _sub(record_wrap, "lido:recordType")
    _sub(record_type, "lido:conceptID", LIDO_TERMS["single_object"], lido__type=LIDO_TERMS["uri"],
         lido__source=LIDO_TERMINOLOGY_SOURCE)
    _sub(record_type, "lido:term", "Einzelobjekt")
    _legal_body(record_wrap, "lido:recordSource", isil=isil, name=institution["name"],
                website=institution["website"])

    record_rights = _sub(record_wrap, "lido:recordRights")
    rights_uri = record_rights_uri(config)
    _rights_type(record_rights, rights_uri, _clean_text(config.get("record_rights_label")) or license_label(rights_uri))
    if config.get("record_rights_holder") and institution["name"]:
        _legal_body(record_rights, "lido:rightsHolder", isil=isil, name=institution["name"])
    for _rule, item in target_items(RECORD_RIGHTS_CREDIT_TARGET):
        _sub(record_rights, "lido:creditLine", item.text)

    record_info = _sub(record_wrap, "lido:recordInfoSet")
    _sub(record_info, "lido:recordInfoLink", record_info_link)
    if ctx.record.updated_at:
        _sub(record_info, "lido:recordMetadataDate", ctx.record.updated_at,
             lido__type=LIDO_TERMS["record_modified"])
    elif ctx.record.created_at:
        _sub(record_info, "lido:recordMetadataDate", ctx.record.created_at,
             lido__type=LIDO_TERMS["record_created"])

    resource_wrap = _sub(administrative, "lido:resourceWrap")
    if resource_sets_enabled(config):
        for media in _public_media(ctx):
            _resource_set(resource_wrap, ctx, media, config, institution)
    else:
        for _rule, item in target_items(RESOURCE_LINK_TARGET):
            representation = _sub(_sub(resource_wrap, "lido:resourceSet"), "lido:resourceRepresentation")
            _sub(representation, "lido:linkResource", item.text)

    _prune_empty(lido)
    _dedupe(lido)
    return wrap if wrap_envelope else lido
