---
type: Decision
title: Inherited Fields — Denormalisierung nur in Elasticsearch, Kaskade max. 1 Ebene
description: Felder verlinkter Records werden für Facettierung in den ES-Index eingebettet; Postgres-Relationstabelle bleibt unverändert Source of Truth; Reindex-Kaskade bewusst auf eine Ebene begrenzt.
tags: [elasticsearch, relationen, suche, performance]
timestamp: 2026-06-05T05:32:38Z
---

# Kontext

Beispiel: Ein Object ist mit einer Occurrence (Publikationsjahr 1905)
verknüpft. Damit Portal-Suche nach "Jahr: 1905" auch dieses Object
findet, müssten Felder der verlinkten Occurrence im Object durchsuchbar
sein — ohne das Datenmodell selbst zu verändern (Issue #213).

# Entscheidung

Denormalisierung passiert **ausschließlich in Elasticsearch**, die
`relations`-Tabelle in Postgres bleibt unverändert Source of Truth.
Konfiguration pro Relation-Feld über
`field_definitions.settings.inherited_fields[]` (Liste der zu
embeddenden Quellfelder). ES-Dokumentstruktur: `linked_<type>[]`-Arrays
mit verschachteltem `inherited`-JSONB-Objekt.

**Reindex-Kaskade ist bewusst auf 1 Ebene begrenzt**: ändert sich ein
verlinkter Record, werden alle darauf verweisenden Records neu indiziert
— aber nicht wiederum deren Verweiser. Das verhindert kombinatorische
Reindex-Explosion bei tief verketteten Relationen.

# Begründung

Datenbank-Schema unverändert zu lassen hält die relationale Struktur
sauber und migrationsfrei; die Duplikation existiert nur dort, wo sie
gebraucht wird (Suchindex). Die 1-Ebenen-Grenze ist ein bewusster
Trade-off: volle Transitivität wäre bei großen Relationsgraphen
(10.000+ verlinkte Records) nicht mehr batchbar ohne signifikante
Zusatzinfrastruktur.

# Status

Feature wurde bei der Beta-Priorisierung von "sofort" auf "vor oder kurz
nach Beta-Start" zurückgestuft — kein Blocker für den öffentlichen
Beta-Start (siehe [Beta-Release-Scope](beta-release-scope.md)).

# Citations

[1] GitHub Issue #213 "Denormalized Relation Fields in Elasticsearch Index"
[2] Session-Discovery 2026-06-05: "Issue #213 — Denormalized Relation Fields in Elasticsearch Index"
