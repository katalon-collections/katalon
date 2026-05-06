# Katalon – Fortschrittsplan

> Letzte Aktualisierung: 2026-05-04

## Implementierungsstatus

| Phase | Beschreibung                                                      | Status                                                                                  |
|-------|-------------------------------------------------------------------|-----------------------------------------------------------------------------------------|
| 0     | Infra (Docker Compose, Dockerfiles, pyproject.toml, config, main) | ✅ Fertig                                                                                |
| 1     | Core-DB (ORM-Models, Alembic-Init + erste Migration)              | ✅ Fertig                                                                                |
| 2     | Schema-Engine (field_definitions, Vokabulare)                     | ✅ Fertig                                                                                |
| 3     | CRUD alle 4 Typen + Relationen                                    | ✅ Fertig (alle 4 Typen + Relationen)                                                    |
| 4     | Auth (JWT, Rollen) + Audit Log                                    | ✅ Fertig                                                                                |
| 5     | Media & IIIF (Upload, Celery, Cantaloupe)                         | ✅ Grundgerüst fertig                                                                    |
| 6     | Admin-UI (React + TypeScript, alle Screens)                       | ✅ Fertig                                                                                |
| 7     | Elasticsearch + Versionierung (Snapshots)                         | ✅ Fertig (ES-Client, Search-Service, Celery-Reindex, GET /v1/search)                    |
| 8     | Public-Portal (React) + Theme-System (Drop-in Bundles)            | ✅ Fertig (Homepage, Suche, Detail, Theme-aware)                                         |
| 9     | Authority-Plugin-System (GND, Geonames)                           | ✅ Fertig (ABC, GND/Geonames-Adapter, /v1/authority/search+fetch)                        |
| 10    | Smart Importer (Excel/CSV ETL)                                    | ✅ Fertig (CSV-Parse, Mapping, Dry-Run, Celery-Import, /v1/importer)                     |
| 11    | OAI-PMH                                                           | ✅ Fertig (Identify, ListRecords, GetRecord, ListSets, ListMetadataFormats, Dublin Core) |
| 12    | Hardening (Rate Limiting, Performance)                            | ✅ Fertig (slowapi 200 req/min, Unit-Tests health+importer+oai)                          |

---

## Post-MVP Erweiterungen (umgesetzt)

| Feature                                        | Branch / Commit       | Beschreibung                                                      |
|------------------------------------------------|-----------------------|-------------------------------------------------------------------|
| Statische Seiten (Admin)                       | feat/static-pages     | ScreenPages, CRUD `/v1/pages`                                     |
| Facetten-Konfiguration (Portal-Settings)       | —                     | `facet_fields` in PortalConfig                                    |
| Portal-Farbkonfiguration                       | fix/pages-sidebar-…   | `color_tokens` JSONB, Migration 0008, Color-Picker in Settings    |
| Logo-Upload                                    | fix/pages-sidebar-…   | `POST /v1/portal/logo`, `GET /v1/portal/logo/file`, Upload-UI     |
| Settings nur für Admins                        | fix/pages-sidebar-…   | Route-Guard in AppShell, Sidebar-Filter                           |
| Schema-Import Hilfe                            | fix/pages-sidebar-…   | `<details>`-Hilfetext mit YAML-Beispiel im ImportModal            |

---

## Nächste Aufgaben (priorisiert)

### Priorität 1 — Relation-Facetten im Portal (Issue #83)

Beim Objekt-Browsing nach verknüpften Entitäten/Orten/Occurrences filtern können.

**Technischer Ansatz:**
- Denormalisierung: beim Indexieren eines Objekts Titel der verknüpften Records als `related_entities`, `related_places`, `related_occurrences` (keyword) in ES-Doc einbetten
- `ensure_index` + `put_mapping` für neue Felder
- Search-API: `rel_entity`/`rel_place`/`rel_occurrence`-Filter, dedizierte Aggregationen
- Portal-Frontend: 3 neue FacetPanels, URL-Params

→ Nach Deployment einmaliger Reindex: `POST /v1/search/reindex`

### Priorität 2 — Portal-Detailseiten

- [#75](https://github.com/karkraeg/Katalon/issues/75) IIIF-Manifest-Link auf ObjectDetailPage
- [#77](https://github.com/karkraeg/Katalon/issues/77) „Zurück zur Suche" — letzte Suchanfrage wiederherstellen
- [#78](https://github.com/karkraeg/Katalon/issues/78) Relation-Type-Labels aus Vokabular auflösen

### Priorität 3 — Langfristig

- CRUD für weitere Admin-Typen (Entity, Place, Occurrence) vollständig ausbauen
- IIIF-Viewer-Integration End-to-End (echte Manifests + Deep Zoom)
- Fehler- und Ladezustände in UI-Screens verbessern

---

## Admin-UI Design-Tokens

- **Fonts:** IBM Plex Sans (UI) + IBM Plex Mono (Monospace)
- **Sidebar:** Dark Navy `#0b1a33`, 236px breit
- **Akzent:** Navy Blue `#1e3a8a`
- **Hintergrund:** `#f4f5f7` (App), `#fff` (Panels)
- **Status-Badges:** Draft (grau), Intern (orange), Öffentlich (grün)

---

## Offene Architektur-Entscheidungen

- [ ] Fuzzy-Datum UI-Komponente: Präzisions-Selektor (Jahr/Monat/Tag + „ca.")
- [ ] Theme-Loader: SSR-inject vs. client-side (kein Flash-of-unstyled-content)
- [ ] Typ-Hierarchien (Untertypen mit eigenen Pflichtfeldern) — Post-MVP
