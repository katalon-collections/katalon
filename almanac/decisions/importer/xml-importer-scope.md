---
title: "XML Importer Scope"
summary: "Katalon's XML importer is generic and selector-driven, with user-chosen record elements and explicit parser safety limits instead of format-specific XML adapters."
topics: [decisions, importer, xml, metadata]
sources:
  - id: decision-note
    type: file
    path: .agents/knowledge/decisions/xml-importer-scope.md
  - id: xml-format
    type: file
    path: backend/src/katalon/services/importer/formats/xml_format.py
  - id: importer-api
    type: file
    path: backend/src/katalon/api/v1/importer.py
  - id: decision-record
    type: file
    path: .agents/knowledge/decisions/xml-importer-scope.md
---

The authoritative rationale and decision status live in the OKF record
`.agents/knowledge/decisions/xml-importer-scope.md` [@decision-record]. This page summarizes the
choice and its implementation; update the OKF record first when changing the decision.


Katalon's XML importer is deliberately generic: it parses XML structure, exposes selectable record elements and tag-path selectors, and leaves institution-specific interpretation to mapping rather than to format-specific parser branches. The planning decision rejects separate MODS, EAD, or Dublin Core locks in favor of one XML handler, user-selected record granularity, and Clark-notation paths with readable labels [@decision-note]. This keeps XML aligned with the [Multi-Format Importer](multi-format-importer), where every source format eventually becomes selectors and source records for the same dry-run and import pipeline.

## Context

XML exports in GLAM systems vary by institution and schema. The planning note names MODS, EAD, and Dublin Core as examples that should pass through the same mechanism instead of receiving separate code paths [@decision-note]. XML uses the same multi-format pipeline as the tabular formats [@xml-format].

The hard part is record granularity. A large XML file may represent one record per direct child, one record per nested element, or one record per domain-specific element. Katalon does not guess that globally; the importer exposes element levels and lets the user choose which Clark-notation tag is one record [@importer-api].

## Decision

`XmlFormat` parses with `lxml` using `resolve_entities=False`, `no_network=True`, `load_dtd=False`, `huge_tree=False`, and `recover=False`, then rejects XML deeper than `max_depth = 64` [@xml-format]. Those parser choices make XML import bounded and non-networked before records reach mapping.

The handler exposes XML-specific discovery before normal selector mapping. `list_element_levels()` returns distinct tags by depth with Clark tags and readable labels, `parse()` yields one `SourceRecord` per selected element, and `list_selectors()` returns scalar tag paths with samples from selected records [@xml-format]. The importer API mirrors that shape: uploaded XML is stored temporarily, `/xml-selectors` accepts an upload ID and record XPath, and the response contains selectors, parsed rows, preview rows, and field-type suggestions [@importer-api].

The scope limit is format interpretation. The XML parser does not know that a MODS title, an EAD unit date, or a Dublin Core creator has project-specific meaning. It gives the mapping UI paths and samples; the user's mapping decides which Katalon fields receive those values [@decision-note] [@xml-format].

## Consequences

The generic design keeps XML import useful across many institutional exports without adding one parser per metadata standard. It also means mapping quality depends on the user choosing the right record element and selectors, so XML has one extra workflow step compared with flat files [@importer-api].

The current importer API enforces a 100 MB `MAX_SIZE`. Raising this limit requires checking backend upload handling, Redis storage, and nginx configuration together [@importer-api].
