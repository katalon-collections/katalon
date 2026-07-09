---
type: Architecture
title: Schema-Engine (field_definitions)
description: Felder pro Primärtyp werden über field_definitions ohne DB-Migration angelegt/geändert/gelöscht (Soft-Delete); nur admin/superuser dürfen das.
tags: [schema-engine, field-definitions, datenmodell]
timestamp: 2026-07-09T00:00:00Z
---

# Wie es funktioniert

Jeder Primärtyp (Object/Entity/Place/Occurrence, siehe
[Vier Bestandstypen](../decisions/vier-bestandstypen.md)) hat konfigurierbare Felder
über `field_definitions` — angelegt/bearbeitet in der Admin-UI unter
**Konfiguration → Schemata**, ohne Datenbankmigration.

- Nur `admin`/`superuser` dürfen Felder anlegen, ändern, löschen.
- Löschen ist Soft-Delete (`is_deleted`) — Feld verschwindet aus der UI, gespeicherte
  Werte in bestehenden Datensätzen bleiben erhalten.
- Neues Feld ist sofort in allen Erfassungsformularen sichtbar; bestehende Datensätze
  ohne Wert bleiben gültig, solange das Feld nicht Pflicht ist.
- `target_subtype` erlaubt Felder, die nur für einen Subtyp gelten (bei Entity und
  Occurrence relevant).
- Export-Mapping (z. B. `oai_dc`) ist pro Feld konfigurierbar; LIDO/METS-MODS-Tabs
  existieren als UI-Stub.

Dasselbe Muster wurde später auf Vokabular-Terme ausgeweitet, siehe
[Vokabular-Custom-Fields](../decisions/vocabulary-custom-fields.md).

# Citations

[1] `docs/02_schema_verwaltung.md`
