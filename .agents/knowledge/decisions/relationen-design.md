---
type: Decision
title: Relationen — flexibel statt feldgebunden, vokabular-typisiert
description: Relation-Felder erlauben Verknüpfung zwischen allen vier Bestandstypen überall im Formular, gefiltert über eine konfigurierbare relation-type-Vokabular statt starrer Feldkonfiguration.
tags: [relationen, datenmodell, ui]
timestamp: 2026-06-26T00:00:00Z
---

# Kontext

CollectiveAccess bindet Relationen oft an feste Stellen in der
Eingabemaske. Für Katalon standen zwei Optionen zur Wahl (Issue #159,
weiterentwickelt in einer späteren Session zur CollectiveAccess-
Relationsschnittstelle):

- **Option A**: Relationen nur dort möglich, wo die Feldkonfiguration
  sie explizit vorsieht (Feldkonfiguration als Gate).
  - Feldkonfiguration = Gatekeeper.
  - Weniger flexibel, aber datenschutz-/disziplin-freundlicher.
- **Option B**: Relationen überall in der Eingabemaske möglich, gefiltert
  über eine konfigurierbare `relation_type`-Vokabular statt hartem
  Feld-Gate.
  - Maximale Flexibilität.
  - Erfordert sorgfältiges Vokabular-Design, um semantisch unsinnige
    Relationen zu vermeiden.

# Entscheidung

Option B — Flexibility-First. Relation-Feld-Konfiguration besteht aus
drei Settings in `field_definitions.settings`:

- `target_type` (Object/Entity/Place/Occurrence)
- `target_subtype` (optional)
- `relation_type_vocab` (Vokabular-Key für die erlaubten Relationstypen)

Relationsdaten selbst liegen als JSONB-Objekte mit `id`, `label`
(denormalisiert für Performance) und `relation_type` in `metadata_`.
Das Formular-Widget bietet debounced Autocomplete-Suche (kein Freitext)
plus Relationstyp-Dropdown pro Eintrag; Backend validiert die
referenzierte UUID gegen die Zieltabelle beim Speichern.

# Begründung

Feldkonfiguration als Gate hätte verhindert, dass Nutzer:innen Objekte
über alle Masken hinweg mit Personen/Orten/Ereignissen verknüpfen
können — das widerspricht dem GLAM-Kernbedarf (Objekt ↔ Person ↔ Ort ↔
Ereignis, beliebig kombinierbar). Governance verschiebt sich damit von
"hartkodierte Feldstruktur" zu "konfigurierbares Vokabular" — im
Einklang mit der Schema-Engine-Philosophie des Projekts.

# Citations

[1] GitHub Issue #159 "feat: relation field — entity/type picker with vocabulary-based relation types"
[2] Session-Entscheidung 2026-06-26: "CollectiveAccess Relation Interface Design: Flexibility-First Approach"
