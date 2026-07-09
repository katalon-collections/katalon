---
type: Decision
title: XML-Importer — generisches Parsing statt formatspezifischer Locks
description: MODS/EAD/Dublin Core werden identisch geparst, Record-Granularität ist UI-gesteuert wählbar, Upload-Limit 500 MB in Phase 1.
tags: [importer, xml, scope]
timestamp: 2026-05-22T00:00:00Z
---

# Kontext

Beim Abschluss der XML-Importer-Planung standen drei offene Fragen im
Raum, die Scope und Implementierungsaufwand direkt beeinflussten.

# Entscheidung

1. **Generisches XML-Parsing ohne Format-Lock**: MODS, EAD, Dublin Core
   etc. werden alle über denselben Mechanismus geparst — kein
   formatspezifischer Code-Pfad. `xml_format.py` bleibt dadurch simpel
   und formatagnostisch; die Interpretation der XML-Struktur passiert
   über den Element-Selector in der UI, nicht im Code.
2. **Record-Granularität ist nutzer-wählbar**: über die
   `StepXmlRecordSelector`-UI-Komponente, statt anzunehmen, welches
   XML-Element ein Record ist.
3. **Upload-Limit 500 MB in Phase 1** (Backend `MAX_SIZE` + nginx
   `client_max_body_size`). Streaming-Uploads für noch größere Dateien
   sind auf Issue #204 verschoben.

Namespace-Strategie: intern Clark-Notation (`{uri}local`), für UI-Labels
menschenlesbares `prefix:local`.

# Begründung

Format-spezifische Parser hätten mit jedem neuen Institutions-Exportformat
neuen Code gebraucht — nicht skalierbar für einen Importer, der beliebige
GLAM-Institutionsexporte verarbeiten soll. Die UI-gesteuerte
Record-Auswahl verschiebt diese Komplexität bewusst zum Menschen, der
seine eigenen Daten kennt, statt sie im Code zu raten. 500 MB deckt die
meisten institutionellen XML-Exports ab, ohne dass Streaming-
Infrastruktur schon in Phase 1 gebaut werden muss.

# Citations

[1] `.agents/XML_IMPORTER_PLAN.md`
[2] Session-Entscheidung 2026-05-22: "Plan finalized with three core architectural decisions documented"
