---
type: Decision
title: "JSON Import ist YAGNI"
tags: [architecture, documentation]
timestamp: 2026-10-30T00:00:00Z
origin: almanac/decisions/importer/json-import-yagni.md
consolidated: 2026-10-30
---

Der Record-Importer unterstützt CSV, Excel und XML als Eingabeformate und könnte technisch um JSON erweitert werden — die `SourceFormat`-ABC und die Mapping/Dry-Run/Import-Pipeline sind formatagnostisch [2]. JSON wird dennoch nicht als Importformat angeboten, weil der praktische Bedarf fehlt und bessere Alternativen existieren.

## Context

Der vorhandene Record-Importer unterstützt CSV/TSV, Excel und XML. Ein zusätzlicher JSON-Dateiimport wurde betrachtet, war aber nicht als benötigter Quellworkflow festgelegt. JSON-Ausgabe und REST-Eingaben sind davon getrennte Schnittstellen.

Technisch wäre ein Flat-JSON-Format (`{"titel": "...", "künstler": "..."}`) mit geringem Aufwand umsetzbar, weil es den CSV-Pfad (Keys = Selektoren, Values = Strings) unverändert wiederverwenden könnte. Nested JSON mit Arrays und bereits getypten Werten wäre dagegen aufwändig: Es bräuchte Pfad-Selektoren wie XML, eine angepasste Mapping-UI (Tree-View statt Spalten-Dropdown) und eine Type-Coercion, die vorhandene Typen respektiert statt alles als String zu behandeln.

## Decision

**JSON-Import für Records wird nicht gebaut.** Die Entscheidung ist ein explizites YAGNI:

1. **Aktueller Umfang:** Für die festgelegten Importabläufe werden CSV/TSV, Excel und XML unterstützt. Ein JSON-Quellformat ist nicht Teil dieses Umfangs; das ist keine Aussage über die Verbreitung von JSON im GLAM-Sektor.
2. **Bestehende Schnittstellen:** Abhängig von der Quellstruktur kann eine explizite Konvertierung oder die REST-API verwendet werden. Verschachtelung, Datentypen und Beziehungen müssen dabei bewusst abgebildet werden.
3. **Export ist kein Importvertrag:** Der JSON-Export allein gewährleistet keinen verlustfreien Re-Import. Ein solcher Workflow bräuchte definierte Abbildungen für verschachtelte Werte, Relationen und Systemfelder.

## Consequences

Der Importer bleibt bei drei Formaten (CSV, Excel, XML). Das hält die Format-Registry, die Mapping-UI und die Dokumentation schlank [1] [2] [4].

Sollte sich der Bedarf später ändern — etwa weil eine große GLAM-Datenquelle flächendeckend JSON-LD oder Activity Streams ausliefert — ist die `SourceFormat`-Schnittstelle stabil genug, um einen `JsonFormat`-Handler nachzurüsten. Die Entscheidung ist reversibel, aber der Aufwand wird nicht vor dem Auftreten eines realen, nicht durch CSV-Konvertierung oder API abdeckbaren Anwendungsfalls investiert.
# Citations

[1] almanac/architecture/workflows/importer-pipeline.md
[2] backend/src/katalon/services/importer/formats/registry.py
[3] backend/src/katalon/services/export_service.py
[4] backend/src/katalon/api/v1/importer.py
