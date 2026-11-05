---
type: Decision
title: Standortverwaltung als eigener Primärtyp, Standortzuweisung über generische Relation
description: StorageLocation ist ein sechster Primärtyp mit Hierarchie (parent_id), analog Collection. Object<->StorageLocation läuft über die generische relations-Tabelle (normal_location/current_location), nicht über eine direkte FK, um SPECTRUM-Standortwechsel-Historie ohne Zusatztabelle abzubilden.
tags: [datenmodell, standortverwaltung, spectrum, relations]
timestamp: 2026-09-03T00:00:00Z
---

**Aktueller Typumfang:** sieben Kerntypen insgesamt; StorageLocation ist der interne Logistiktyp. Die historische Zählung als sechster Typ beschreibt die damalige Erweiterung.


# Kontext

GitHub-Issue #26 dokumentierte die Standortverwaltung als bewusste
Scope-Lücke (CLAUDE.md schloss sie explizit aus). Für SPECTRUM-Kompatibilität
(Procedure "Location and movement control") reicht ein einfacher
`location_id`-FK auf Objekten nicht: SPECTRUM unterscheidet *normal location*
(Heimatstandort) und *current location* (kann durch Leihgabe/Ausstellung/
Restaurierung abweichen) und verlangt eine nachvollziehbare
Bewegungshistorie, nicht nur den überschriebenen aktuellen Zustand.

# Entscheidung

`StorageLocation` ist ein sechster Primärtyp (`storage_locations`-Tabelle),
strukturell identisch zu `Collection`: `id`, `idno`, `storage_location_type`,
selbstreferenzierender `parent_id` (Hierarchie Haus → Raum → Regal → Box,
beliebige Tiefe, `ondelete=SET NULL`), `status`, JSONB `metadata`
(field_definitions-Engine), Timestamps, `version` (optimistic locking).
Kein PostGIS — Innenraum-Hierarchie ist semantisch kein `Place`.

Die Verknüpfung Object↔StorageLocation läuft **nicht** über eine direkte FK,
sondern über die bestehende generische `relations`-Tabelle (siehe
[Generic Relation Model](../../../almanac/decisions/data/generic-relation-model.md)),
mit zwei neuen Relation-Type-Vokabular-Termen `normal_location` und
`current_location` (`applies_from=['object']`, `applies_to=['storage_location']`).
Die Zuweisung ist frei editierbar über den bestehenden generischen
Beziehungen-Mechanismus (RelationInput), nicht an den Procedure-Workflow
gekoppelt — aber im Objektformular über eine eigene Sidebar-Karte
„Zugeordnete Lagerorte" (gleiche Ebene wie Medien/Versionen/Audit-Log/
Verknüpfte Vorgänge) statt in der generischen „Weitere Beziehungen"-Liste
dargestellt. Die Karte erscheint nur, wenn mindestens ein StorageLocation
im System existiert (`storageLocations.list({page_size:1}).total > 0`) —
ohne konfigurierte Lagerorte bleibt das Objektformular unverändert.
Bewegungshistorie ergibt sich aus mehreren
Relation-Zeilen über Zeit (Erstellen/Ändern/Löschen je Relation ist bereits
auditiert für storage_location via `_LOGGABLE_RECORD_TYPES`) — keine
zusätzliche Movement-Log-Tabelle nötig.

`storage_location` ist Teil der Registry für Schema-Engine
(`SCHEMA_TARGET_TYPES`), Subtypen (`PRIMARY_TYPES`/`_TYPE_MODEL_FIELD`),
Relation-Audit (`_LOGGABLE_RECORD_TYPES`) und internen Suchindex — bewusst
**nicht** Teil der öffentlichen Portal-Typen (`browse_enabled_types`,
`PUBLIC_TYPES`) oder des Imports (`VALID_TYPES`). Physischer Standort ist
sicherheitsrelevant (Diebstahlschutz) und bleibt Admin-only.

# Begründung

Eine direkte FK (wie ursprünglich in Issue #26 skizziert) würde jeden
Standortwechsel überschreiben und keine Historie liefern — SPECTRUM-Pflicht
verfehlt. Die generische Relations-Tabelle liefert Historie „gratis" über
mehrere Zeilen plus vorhandenes Audit-Log, ohne eine weitere
pair-spezifische Tabelle einzuführen (siehe Prinzip in
Generic-Relation-Model-Entscheidung). Ein eigener Primärtyp statt
Freitextfeldern erlaubt Navigation/Hierarchie/Wiederverwendung über
mehrere Objekte hinweg.

# Citations

[1] GitHub-Issue #26 „feat: Standortverwaltung (Storage Locations)"
[2] `almanac/decisions/data/generic-relation-model.md`
[3] `backend/src/katalon/core/models.py` (Collection/StorageLocation Modelle)
[4] SPECTRUM Procedure "Location and Movement Control" (spectrum-uk.org)
