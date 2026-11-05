---
type: Decision
title: idno und label bleiben Pflicht-Systemfelder statt schemaabhängig konfigurierbar
description: UUID, idno und label bleiben strikt getrennt; keine Relaxierung der Pflicht, stattdessen dokumentierte Konventionen (Auto-Vergabe, devised title in eckigen Klammern).
tags: [schema, metadata, cataloguing-standards]
timestamp: 2026-09-13T00:00:00Z
---

# Kontext

Diskutiert wurde, ob `idno` (ID-Nr./Inventarnummer) und `label` (Titel) —
beide seit #idno-system-field echte Systemfelder im Schema-Editor — analog
zu gewöhnlichen Feldern schemaabhängig auf "nicht Pflicht" gestellt werden
sollten. Anlass: heterogene Sammlungen (z. B. naturwissenschaftliche Proben)
haben nicht immer einen sinnvollen Titel, und `idno` wird bei manchen
Institutionen automatisch vergeben statt manuell erfasst.

Zwei Alternativen wurden geprüft und verworfen:

1. Pflicht pro Typ/Subtyp konfigurierbar machen (erfordert, `idno`s
   hartkodierte Pflichtprüfung in allen sieben Record-Endpunkten durch einen
   Blick auf die Felddefinition zu ersetzen, plus eine Migration für
   `storage_location.idno`, das anders als die übrigen sechs Typen
   `NOT NULL` in der DB ist).
2. Bei leerem Titel automatisch einen Platzhalter-String (`[Ohne Titel]`)
   persistieren, um alle Lesestellen (Liste, Portal, Suche, PID-Export,
   RDF) auf einen Schlag mit einem echten Wert zu versorgen statt eines
   berechneten Fallbacks an jeder Stelle einzeln.

Vor der Entscheidung wurde geprüft, was etablierte Museums-/Bibliotheks-/
Archivstandards zu Identifikator und Titel sagen: Spectrum/Object ID
(Objektnummer "strictly mandatory"; Object Name ODER Title als Minimum),
RDA 2.3.2.10/2.3.2.11 (Title Proper Core Element, bei fehlendem Titel
"devised title" durch den Katalogisierer, in eckigen Klammern gesetzt) und
ISAD(G) 3.1.2 (Titel mandatory, "supplied title"-Konvention bei fehlendem
Formaltitel).

# Entscheidung

Beide Alternativen werden verworfen. `idno` und `label` bleiben exakt wie
implementiert: echte Pflichtfelder auf Schemaebene, nicht pro Typ/Subtyp
abschaltbar, kein automatisch generierter Platzhaltertext. Stattdessen wird
dokumentiert (`almanac/concepts/metadata/schema-engine.md`, Abschnitt
"System Fields: `idno` And `label`"):

- Die interne UUID (`id`) ist von `idno` und `label` unabhängig und trägt
  keine fachliche Bedeutung.
- `idno` ist die fachliche/institutionelle Kennung zusätzlich zur UUID —
  vergleichbar mit Spectrums Objektnummer, nicht mit optionalen externen
  Bibliotheks-Identifikatoren (ISBN/ISSN/DOI). Wer die manuelle Eingabe
  vermeiden will, konfiguriert `AdminConfig.idno_schemas`/`idno_patterns`
  für automatische Vergabe (`consume_next_idno`).
- `label` bleibt Pflicht, aber Katalon generiert bei fehlendem Titel keinen
  Platzhalter automatisch. Nach RDA/ISAD(G)-Konvention erfasst das
  Fachpersonal in diesem Fall selbst einen kurzen, in eckige Klammern
  gesetzten Ersatztitel (`[Ohne Titel]` oder beschreibender wie
  `[Basaltprobe, Fundort X]`) — das markiert ihn als supplied statt vom
  Objekt übernommen, exakt wie in den Standards vorgesehen.

# Begründung

Beide Regelwerke bestätigen den Ist-Zustand eher, als ihn zu widerlegen:
Identifikator ist überall strikt Pflicht, Titel ebenfalls, nur mit einer
etablierten Ausweichkonvention für den Leerfall statt einer Lockerung der
Pflicht. Ein software-generierter Platzhalter (`[Ohne Titel]`) würde die
Pflicht zwar technisch immer erfüllen, aber den fachlichen Anspruch eines
"devised title" (kurze, beschreibende Ersatzformulierung) nicht einlösen —
das bleibt bewusst eine Katalogisierungsentscheidung des Personals, keine
Automatik. Eine schemaabhängige Pflicht-Konfiguration hätte zudem echten
Umbau erfordert (sieben Endpunkte, eine DB-Migration) für einen Nutzen, den
die Standards nicht stützen.

# Citations

[1] `backend/src/katalon/main.py` (`_ensure_label_fields`, `_ensure_idno_fields`)
[2] `backend/src/katalon/api/v1/objects.py` (hartkodierte idno-Pflichtprüfung, Muster in allen sieben Typen)
[3] `backend/src/katalon/core/models.py` (`idno`-Spalte, `storage_location` als einziger NOT-NULL-Ausreißer)
[4] `almanac/concepts/metadata/schema-engine.md` (Abschnitt "System Fields: `idno` And `label`")
