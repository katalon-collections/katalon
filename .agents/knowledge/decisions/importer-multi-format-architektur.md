---
type: Decision
title: Importer — Plugin-Architektur statt format-spezifischer Funktionen
description: SourceFormat-ABC mit sniff/parse/list_selectors-Interface plus Format-Registry ersetzt separate parse_csv/parse_excel-Funktionen, ohne Breaking Changes.
tags: [importer, architektur, refactoring]
timestamp: 2026-05-19T14:43:16+02:00
---

# Kontext

CSV- und Excel-Import-Logik war ursprünglich als getrennte
`parse_csv`/`parse_excel`-Funktionen in `importer_service`
implementiert. Mit XML als drittem Quellformat (siehe
[XML-Importer-Scope](xml-importer-scope.md)) und absehbar weiteren
Formaten wurde eine gemeinsame Abstraktion nötig.

# Entscheidung

`SourceFormat`-ABC mit einheitlichem Interface (`sniff`, `parse`,
`list_selectors`), `CsvFormat`- und `ExcelFormat`-Plugins implementieren
es, eine Format-Registry übernimmt automatische Formaterkennung.
`XmlFormat` existiert vorerst als Stub (`NotImplementedError`) für eine
spätere Phase.

`importer_service.parse_csv`/`parse_excel` bleiben als
Backwards-Compat-Wrapper erhalten — keine Änderungen an API-Endpoints
oder Workern nötig, alle 20 bestehenden Importer-Tests bleiben grün.

# Begründung

Ohne gemeinsames Interface hätte jedes neue Format eigene
Sonderbehandlung an jeder Call-Site erzwungen (API, Worker, UI).
Die Registry macht Formaterkennung erweiterbar, ohne bestehenden Code
anzufassen — neues Format = neue Plugin-Klasse + Registrierung, sonst
nichts.

# Citations

[1] Commit `fe9b9ca` "refactor(B1): multi-format architecture with SourceFormat ABC and registry"
