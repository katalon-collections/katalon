---
type: Decision
title: Vier Bestandstypen mit getrennten Tabellen
description: Object/Entity/Place/Occurrence sind vier eigene DB-Tabellen, alle mit frei konfigurierbaren Metadaten über field_definitions.
tags: [datenmodell, schema-engine]
timestamp: 2026-07-09T00:00:00Z
---

# Kontext

Ein generisches Intrinsic-/Attribute-System mit einer zentralen Tabelle
für alle Bestandsobjekte macht Datenbank-Constraints und Abfragen
unnötig kompliziert. Katalon setzt stattdessen auf vier fachlich
getrennte primäre Typen.

# Entscheidung

Vier getrennte Tabellen für Bestandsdaten:

| Typ        | DB-Tabelle    | Beschreibung                         |
|------------|---------------|---------------------------------------|
| Object     | `objects`     | Artefakte: Fotos, Dokumente, Gemälde |
| Entity     | `entities`    | Personen, Organisationen             |
| Place      | `places`      | Geografische Orte (PostGIS)          |
| Occurrence | `occurrences` | Werke (FRBR), Ereignisse, Konzepte   |

Alle vier Typen haben dynamisch konfigurierbare Metadaten via
`field_definitions` (siehe Schema-Engine in `KONZEPT.md`). Ein fünfter
Typ, Procedure (Leihverkehr, Erwerbung, Restaurierung), ist bewusst
separat gehalten statt als fünfte gleichrangige Bestandstabelle.

Alle vier Typen können beliebig über eine generische `relations`-Tabelle
miteinander verknüpft werden, mit Metadaten auf der Relation selbst.

# Begründung

Getrennte Tabellen statt einer generischen Intrinsic-Tabelle:
klareres Schema, bessere Query-Performance, PostGIS lässt sich direkt
auf `places` anwenden statt über ein generisches Attribut-System.

# Citations

[1] Root `CLAUDE.md`, Abschnitt "Vier Bestands-Typen"
[2] `KONZEPT.md`, Datenmodell-Abschnitt
