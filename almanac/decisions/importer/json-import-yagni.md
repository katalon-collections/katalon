---
title: "JSON Import ist YAGNI"
summary: "Ein JSON-Import-Format für den Record-Importer wird bewusst nicht gebaut, weil Metadatendaten außerhalb von IIIF-Manifesten praktisch nie als JSON vorliegen und existierende Alternativen den Bedarf abdecken."
topics: [decisions, importer, architecture, metadata]
sources:
  - id: importer-pipeline
    type: file
    path: almanac/architecture/workflows/importer-pipeline.md
  - id: format-registry
    type: file
    path: backend/src/katalon/services/importer/formats/registry.py
  - id: export-service
    type: file
    path: backend/src/katalon/services/export_service.py
  - id: import-api
    type: file
    path: backend/src/katalon/api/v1/importer.py
---

Der Record-Importer unterstützt CSV, Excel und XML als Eingabeformate und könnte technisch um JSON erweitert werden — die `SourceFormat`-ABC und die Mapping/Dry-Run/Import-Pipeline sind formatagnostisch [@format-registry]. JSON wird dennoch nicht als Importformat angeboten, weil der praktische Bedarf fehlt und bessere Alternativen existieren.

## Context

GLAM-Metadaten liegen typischerweise als CSV, Excel (Kuratoren-Alltag) oder XML (LIDO, MODS, EAD, DC) vor. JSON als Transportformat für Bestandsdaten ist im GLAM-Sektor selten — die einzige nennenswerte Ausnahme sind IIIF-Manifests, und selbst dort ist der Import-Pfad über die API sinnvoller als ein Bulk-Import über Datei-Upload.

Technisch wäre ein Flat-JSON-Format (`{"titel": "...", "künstler": "..."}`) mit geringem Aufwand umsetzbar, weil es den CSV-Pfad (Keys = Selektoren, Values = Strings) unverändert wiederverwenden könnte. Nested JSON mit Arrays und bereits getypten Werten wäre dagegen aufwändig: Es bräuchte Pfad-Selektoren wie XML, eine angepasste Mapping-UI (Tree-View statt Spalten-Dropdown) und eine Type-Coercion, die vorhandene Typen respektiert statt alles als String zu behandeln.

## Decision

**JSON-Import für Records wird nicht gebaut.** Die Entscheidung ist ein explizites YAGNI:

1. **Kein praktischer Bedarf:** CSV dominiert den Kuratoren-Alltag, XML deckt den Austausch mit Fremdsystemen ab. JSON-Datenquellen existieren im GLAM-Sektor praktisch nicht außerhalb von IIIF — und für IIIF-Manifests ist die REST-API der natürliche Einstiegspunkt, nicht ein Datei-Upload.
2. **Alternativen decken den seltenen Fall ab:** Wer strukturierte JSON-Daten importieren will, kann sie vorab in CSV konvertieren (jedes Scripting-Tool kann das) oder die REST-API verwenden (`POST /v1/objects`, etc.).
3. **Export existiert bereits als JSON:** Der `export_service` kann Records als JSON streamen [@export-service]. Das deckt den Re-Import-Fall (Export → Bearbeiten → Import) ab, denn ein JSON-Export kann trivial nach CSV konvertiert und über den bestehenden CSV-Import wieder eingespielt werden.

## Consequences

Der Importer bleibt bei drei Formaten (CSV, Excel, XML). Das hält die Format-Registry, die Mapping-UI und die Dokumentation schlank [@importer-pipeline] [@format-registry] [@import-api].

Sollte sich der Bedarf später ändern — etwa weil eine große GLAM-Datenquelle flächendeckend JSON-LD oder Activity Streams ausliefert — ist die `SourceFormat`-Schnittstelle stabil genug, um einen `JsonFormat`-Handler nachzurüsten. Die Entscheidung ist reversibel, aber der Aufwand wird nicht vor dem Auftreten eines realen, nicht durch CSV-Konvertierung oder API abdeckbaren Anwendungsfalls investiert.