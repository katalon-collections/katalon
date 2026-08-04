---
title: "Multi-Format Importer"
summary: "Katalon's importer uses a shared SourceFormat registry and selector-based mapping so CSV, Excel, and XML follow one upload, mapping, and dry-run workflow."
topics: [decisions, importer, architecture, metadata]
sources:
  - id: decision-note
    type: file
    path: .agents/knowledge/decisions/importer-multi-format-architektur.md
  - id: format-base
    type: file
    path: backend/src/katalon/services/importer/formats/base.py
  - id: format-registry
    type: file
    path: backend/src/katalon/services/importer/formats/registry.py
  - id: importer-service
    type: file
    path: backend/src/katalon/services/importer_service.py
  - id: importer-api
    type: file
    path: backend/src/katalon/api/v1/importer.py
---

Katalon's importer is multi-format because CSV, Excel, and XML sources enter one shared mapping and dry-run model instead of branching into separate import subsystems. A `SourceFormat` abstraction defines detection, parsing, and selector listing; the registry chooses the first matching handler in Excel, CSV, XML order [@format-base] [@format-registry]. The mapping layer then treats CSV columns, Excel headers, and XML tag paths as selectors, so the [Importer Pipeline](../../architecture/workflows/importer-pipeline) can validate and transform rows through one backend path [@importer-api] [@importer-service].

## Context

The recorded decision says CSV and Excel parsing existed before XML work pushed the importer toward a common format boundary [@decision-note]. Without that boundary, every new source format would require special cases at upload, mapping, dry-run, worker, and UI call sites. XML made the pressure visible because it is not flat, but it still needs the same downstream behavior as a spreadsheet once the user has chosen record elements and selectors.

## Decision

Format-specific code stops at the `SourceFormat` interface. Each handler implements `sniff()`, `parse()`, and `list_selectors()`, while `Selector` gives the mapping UI a path, label, sample, and kind [@format-base]. The registry owns format detection and currently registers `ExcelFormat`, `CsvFormat`, and `XmlFormat`, with Excel first because it uses magic-byte detection and should run before simpler filename or text checks [@format-registry].

The importer API accepts mappings as `selector -> MappingEntry`, where a selector is a CSV or Excel column header or an XML Clark-notation path [@importer-api]. `apply_mapping()` normalizes both simple mappings and transform-bearing mappings, reads values by selector from parsed rows, applies transforms, handles `__idno__`, and coerces values according to field definitions when available [@importer-service]. `dry_run()` uses the same mapping shape to compute required-field warnings, type warnings, schema validation input, vocabulary statistics, and preview rows [@importer-service].

This decision is paired with [XML Importer Scope](xml-importer-scope). XML adds an element-selection step before mapping, but after selectors are produced it joins the same selector-based pipeline as CSV and Excel [@importer-api].

## Consequences

The importer has one semantic contract for preview and import. Format handlers convert bytes into source records and selectors; importer services decide how selectors become Katalon metadata [@format-base] [@importer-service]. That keeps format detection extensible without duplicating validation, transforms, ID number handling, or vocabulary reconciliation.

The tradeoff is that every format must fit the selector model. CSV and Excel fit naturally because headers are selectors; XML needs Clark-notation tag paths and a separate record-selection step to become flat enough for the shared pipeline [@importer-api]. Maintainers adding another source format should add a `SourceFormat` implementation and registry entry before changing `apply_mapping()` or dry-run behavior.
