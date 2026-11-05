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
  - id: decision-record
    type: file
    path: .agents/knowledge/decisions/json-import-yagni.md
---

The authoritative rationale and decision status live in the OKF record
`.agents/knowledge/decisions/json-import-yagni.md` [@decision-record]. This page summarizes the
choice and its implementation; update the OKF record first when changing the decision.


Der Record-Importer unterstützt CSV, Excel und XML als Eingabeformate und könnte technisch um JSON erweitert werden — die `SourceFormat`-ABC und die Mapping/Dry-Run/Import-Pipeline sind formatagnostisch [@format-registry]. JSON wird dennoch nicht als Importformat angeboten, weil der praktische Bedarf fehlt und bessere Alternativen existieren.


## Current Contract

**JSON-Import für Records wird nicht gebaut.** Die Entscheidung ist ein explizites YAGNI:

1. **Aktueller Umfang:** Für die festgelegten Importabläufe werden CSV/TSV, Excel und XML unterstützt. Ein JSON-Quellformat ist nicht Teil dieses Umfangs; das ist keine Aussage über die Verbreitung von JSON im GLAM-Sektor.
2. **Bestehende Schnittstellen:** Abhängig von der Quellstruktur kann eine explizite Konvertierung oder die REST-API verwendet werden. Verschachtelung, Datentypen und Beziehungen müssen dabei bewusst abgebildet werden.
3. **Export ist kein Importvertrag:** Der JSON-Export [@export-service] allein gewährleistet keinen verlustfreien Re-Import. Ein solcher Workflow bräuchte definierte Abbildungen für verschachtelte Werte, Relationen und Systemfelder.

## Implementation Constraints

Der Importer bleibt bei drei Formaten (CSV, Excel, XML). Das hält die Format-Registry, die Mapping-UI und die Dokumentation schlank [@importer-pipeline] [@format-registry] [@import-api].

Sollte sich der Bedarf später ändern — etwa weil eine große GLAM-Datenquelle flächendeckend JSON-LD oder Activity Streams ausliefert — ist die `SourceFormat`-Schnittstelle stabil genug, um einen `JsonFormat`-Handler nachzurüsten. Die Entscheidung ist reversibel, aber der Aufwand wird nicht vor dem Auftreten eines realen, nicht durch CSV-Konvertierung oder API abdeckbaren Anwendungsfalls investiert.