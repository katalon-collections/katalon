---
type: Decision
title: Import löst Text zu Vokabelterm und Relationsziel in einem Pfad auf, der Dry-run rollt ihn zurück
status: accepted
date: 2026-11-05
---

# Kontext

Relationsspalten (z. B. `werk`, `Publisher`) hatten im Import keine Auflösung, Vokabelspalten nur im
Worker und nur gegen den Term-Code. Der Dry-run gab rohe Texte an `validate_metadata` und scheiterte
mit "muss ein Objekt sein", obwohl der echte Import funktioniert hätte. Kuratierte Terme wurden nicht
über ihr Label gefunden, `Vokabular erweitern` legte Duplikate an.

# Entscheidung

`services/import_resolution.py` enthält `resolve_vocab_terms` und `resolve_relations`. Worker und
Dry-run rufen dieselben Funktionen auf. Der Dry-run legt fehlende Terme und (bei `on_missing: create`)
fehlende Relationsziele in einem Savepoint an, validiert und rollt den Savepoint zurück. Pro
Relationsfeld wählt der User `lookup` (`idno` Standard, `label`) und `on_missing` (`error` Standard,
`create`). Vokabular wird gegen Code und alle Sprach-Labels verglichen; ein Label, das auf mehrere
Datensätze oder Terme passt, ist immer ein Fehler.

# Begründung

Eine Auflösung statt zwei verhindert, dass Vorschau und Import auseinanderlaufen. Der Savepoint-Rollback
validiert das echte Ergebnis (Ziel-IDs existieren, Relationstyp passt) ohne einen zweiten Platzhalter-Pfad.
ID-Nummer als Standard ist eindeutig; Labels sind es nicht. Anlegen fehlender Ziele ist wählbar, weil es
bei Tippfehlern Duplikate und halb leere Entwürfe erzeugt.

# Konsequenzen

- Der Dry-run schreibt kurz in die Datenbank (idno-Zähler, Audit-Eintrag, Entwurf), alles im Savepoint.
- Relations-Unterfelder in Gruppen und Relationsfelder ohne `fixed_relation_type` werden nicht aufgelöst
  (Zeilenfehler).
- `sync_schema_relations` lädt Felder weiterhin nur nach `target_type`, nicht nach Subtyp. Das ist ein
  getrennter, offener Fehler.

# Citations

- `backend/src/katalon/services/import_resolution.py`
- `backend/src/katalon/api/v1/importer.py`
- `backend/src/katalon/workers/import_tasks.py`
