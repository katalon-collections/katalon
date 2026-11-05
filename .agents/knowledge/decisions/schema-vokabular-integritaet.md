---
type: Decision
title: Schema- und Vokabularintegrität — Legacy-Felder erhalten, Vokabularlöschung nur mit Warnung/Remapping-Angebot
description: Unbekannte historische Metadatenfelder werden unvalidiert im Record erhalten statt abgelehnt oder still entfernt; Vokabularterme mit Referenzen dürfen weiterhin gelöscht werden, aber erst nach Warnung mit Nutzungszahl und angebotenem Remapping-Dialog, kein stiller Datenverlust (#394).
tags: [datenmodell, schema, vokabular, backend, integrität]
timestamp: 2026-09-13T00:00:00Z
---

# Kontext

Production-Readiness-Audit (`docs/production-readiness-audit-2026-09-13.md`,
Abschnitte „Das dynamische Schema wird backendseitig nicht vollständig
erzwungen“ und „Vokabularlöschung bewahrt Text, nicht referenzielle
Integrität“): `metadata_` ist ein freies `dict[str, Any]`; Records können
Feldwerte enthalten, die nicht mehr in `field_definitions` konfiguriert sind
(Feld wurde nach Anlage des Records aus dem Schema entfernt — betrifft nicht
nur importierte Altdaten, sondern jeden Record, dessen Schema sich seither
geändert hat). Vokabularterme werden hart gelöscht (`vocabularies.py:329-345`)
ohne Usage-Guard; referenzierende Records behalten eine tote UUID. Issue #394.

# Entscheidung

**1. Unbekannte/nicht mehr im Schema definierte Metadatenfelder: als Legacy
erhalten, nicht ablehnen, nicht still entfernen.** Ein Feldwert in
`metadata_`, für den `field_definitions` (für den jeweiligen `target_type`)
keinen aktiven Eintrag mehr hat, bleibt beim Speichern unverändert im Record
stehen und wird nicht validiert (kein Pflicht-/Format-/Typcheck). Speichern
anderer Felder wird dadurch nicht blockiert. Die Admin-UI zeigt solche Felder
in einem eigenen „Nicht im Schema“-Block, read-only markiert nach Typ,
editierbar nur als Freitext-Entfernen. Sie bleiben intern gespeichert und sind
nicht facettierbar (kein Schema-Eintrag). Die frühere pauschale Aussage zu
Volltext und Export ist durch die öffentliche Projektion eingeschränkt:
Unbekannte Felder ohne aktive öffentliche Definition gelangen weder in
öffentliche Ausgaben noch in den daraus gebauten Suchindex. Authentifizierte
Rohdatenexporte sind davon zu unterscheiden. Diese
Regel gilt unabhängig vom Alter des Records — nicht „historische Daten vor
Katalon“, sondern „Feld ist aktuell nicht mehr im Schema definiert“.
Verworfen: Ablehnen bei Schreibzugriff (macht alte Records unbearbeitbar, bis
jemand das Altfeld manuell entfernt oder ins Schema zurückholt — unnötige
Reibung für unbeteiligte Edits) und automatisches Entfernen (stiller
Datenverlust, verstößt gegen die Acceptance-Criteria aus #394).

**2. Vokabularterm-Löschung: Guard mit Warnung + Remapping-Angebot, aber kein
Zwang zum Remapping.** `DELETE` auf einen referenzierten Term liefert
zunächst die Nutzungszahl und bietet einen Remapping-Dialog an („N Records
verweisen auf diesen Term — auf welchen Ersatzterm umhängen, oder trotzdem
löschen?“). Remapping schreibt betroffene Referenzen serverseitig um (Batch-
Update + Reindex) bevor der Term entfernt wird. Der Kurator kann das
Remapping aber auch explizit überspringen und trotzdem löschen — dann bleibt
die tote UUID-Referenz in den betroffenen Records stehen, exakt wie im
Soft-Delete-Fall (siehe
[Soft-Delete-Relationsvertrag](soft-delete-relationsvertrag.md)) mit einem
„Term gelöscht“-Badge statt des Termlabels. Entscheidend gegenüber dem
Status quo: die tote Referenz entsteht nie mehr *unbemerkt* — der Kurator
wird vor dem Löschen explizit informiert und bestätigt bewusst. Verworfen:
harter Blocker ohne Bypass (zu unflexibel für seltene, aber legitime
Aufräumfälle) und Pflicht-Remapping ohne Bypass-Option (erzwingt für jeden
Löschvorgang einen Ersatzterm, den es fachlich nicht immer gibt).

**3. Umfang unverändert gegenüber Issue #394**, insbesondere: konsistente
Validierung von number/boolean/geo/vocab/vocab-free/relation/Gruppenfeldern
auf jedem Schreibpfad, Ablehnung ungültiger Feldkonfigurationen (Regex) bei
Konfigurationszeit, Zyklusprüfung im Vokabularimport, gleicher Vertrag für
CRUD/Import/Batch/API — diese Punkte sind keine Fachentscheidung, sondern
Umsetzungsarbeit, siehe Issue.

# Begründung / Scope-Grenzen

- Kein zeitbasiertes „Legacy“-Flag, keine Unterscheidung zwischen „vor
  Katalon importiert“ und „Feld letzte Woche aus dem Schema entfernt“ — die
  Regel ist rein strukturell (Feld aktuell definiert oder nicht), das ist
  einfacher zu implementieren und zu testen als ein Zeitstempel-Grenzfall.
- Bewusst kein Tombstone für Vokabularterme (kein `is_deleted`-Flag am Term):
  Guard+Remapping-Dialog löst das gleiche Problem (keine unbemerkte tote
  Referenz) ohne neue Spalte, ohne Filterlogik an jeder Stelle, wo Terme
  gelistet werden.
- Der Bypass beim Löschen ist eine bewusste Abweichung von „nie tote UUID“
  hin zu „nie *unbemerkt* tote UUID“ — spiegelt die reale Kuratorenarbeit
  (manchmal ist ein Term schlicht falsch angelegt und hat keinen sinnvollen
  Nachfolger).

# Citations

- `docs/production-readiness-audit-2026-09-13.md` — Abschnitte „Das dynamische
  Schema wird backendseitig nicht vollständig erzwungen“, „Vokabularlöschung
  bewahrt Text, nicht referenzielle Integrität“
- `backend/src/katalon/services/schema_service.py:103-116`, `:264-274`,
  `:393-407`
- `backend/src/katalon/api/v1/vocabularies.py:329-345`
- `backend/src/katalon/services/vocabulary_import_service.py:270-355`
- GitHub-Issue #394
