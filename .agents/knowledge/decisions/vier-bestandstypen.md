---
type: Decision
title: Sieben Kerntypen mit getrennten Tabellen
description: Sieben eigenständige Tabellen für fünf öffentliche Bestands-/Sammlungstypen, interne Lagerorte und Vorgänge; gemeinsame Schema-Engine und Relationen.
tags: [datenmodell, schema-engine]
timestamp: 2026-07-09T00:00:00Z
---

# Kontext

Die ursprüngliche Entscheidung vom Juli 2026 trennte Object, Entity, Place und
Occurrence statt einer generischen Intrinsic-Tabelle. Collection und
StorageLocation erweiterten später dasselbe Prinzip. Der Dateiname bleibt
für bestehende Verweise erhalten; er bezeichnet nicht die heutige Typzahl.

# Entscheidung

Sieben Kerntypen besitzen jeweils eine eigene Tabelle:

| Typ | Tabelle | Fachliche Rolle |
|---|---|---|
| object | objects | Sammlungsgut und Digitalisate |
| entity | entities | Personen und Körperschaften |
| place | places | Geografische Orte mit PostGIS |
| occurrence | occurrences | Werke, Ereignisse und Konzepte |
| collection | collections | Sammlungen und hierarchische Bestände |
| storage_location | storage_locations | Interne Lagerorte mit Hierarchie |
| procedure | procedures | Vorgänge mit Prozessstatus und Fristen |

Alle nutzen dynamische Metadaten über `field_definitions`, Versionen und die
allgemeine Relationstabelle. Die ersten fünf Typen können öffentlich sein;
Lagerorte bleiben intern, Vorgänge sind Prozessdaten. Lagerorte haben keinen
Publikationsstatus; Vorgänge verwenden einen eigenen Prozessstatus.
`vocabulary_term` ist ein zusätzlicher Schema-Zieltyp, kein achter Kerntyp.

Die getrennten Tabellen ermöglichen fachliche Constraints, Place-Geometrie
und Vorgangsregeln ohne eine generische Tabelle mit allen Sonderfällen.
Typübergreifende Funktionen müssen die jeweils passende Registry verwenden:
der generische Metadatenimport unterstützt weiterhin nur vier Typen, öffentliche
Portal-Reads fünf. Siehe [Standortverwaltung](standortverwaltung.md).

# Begründung

Getrennte Tabellen statt einer generischen Intrinsic-Tabelle:
klareres Schema, bessere Query-Performance, PostGIS lässt sich direkt
auf `places` anwenden statt über ein generisches Attribut-System.

# Citations

[1] `backend/src/katalon/core/schemas.py` — `RECORD_TYPES`
[2] `backend/src/katalon/core/models.py` — sieben Record-Modelle
[3] `backend/src/katalon/api/v1/schema_admin.py` — `SCHEMA_TARGET_TYPES`
[4] `almanac/architecture/cross-cutting-record-contract.md` — Registry-Grenzen
[5] `KONZEPT.md`, Datenmodell
