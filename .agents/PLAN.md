# Katalon – Fortschrittsplan

> Letzte Aktualisierung: 2026-05-25

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
| 9     | Authority-Plugin-System (GND, Geonames, VIAF, Wikidata, TGN, ICONCLASS) | ✅ Fertig (6 Adapter, DB-Registry, 41 Unit-Tests, /v1/authorities/search+fetch)     |
| 10    | Smart Importer (Excel/CSV ETL)                                    | ✅ Fertig (CSV-Parse, Mapping, Dry-Run, Celery-Import, /v1/importer)                     |
| 11    | OAI-PMH                                                           | ✅ Fertig (Identify, ListRecords, GetRecord, ListSets, ListMetadataFormats, Dublin Core) |
| 12    | Hardening (Rate Limiting, Performance)                            | ✅ Fertig (slowapi 200 req/min, Unit-Tests health+importer+oai)                          |

---

## Post-MVP Erweiterungen (umgesetzt)

| Feature                                        | PR    | Beschreibung                                                                          |
|------------------------------------------------|-------|---------------------------------------------------------------------------------------|
| Statische Seiten (Admin)                       | #80   | ScreenPages, CRUD `/v1/pages`                                                         |
| Containerfelder (nested metadata groups)       | #220  | `field_type = "group"`, `parent_id` FK, nested ES mapping (Closes #220)               |
| Benutzer-Verwaltungs-Screen                    | #144  | User-CRUD: Liste, Anlegen, Rolle ändern, Deaktivieren, Löschen, API-Keys (Closes #144) |
| Relationen-Panel im Admin-Formular             | —     | Inline-Edit für Relation-Metadaten, Gegenrichtung-Indikator                           |
| Facetten-Konfiguration (Portal-Settings)       | —     | `facet_fields` in PortalConfig                                                        |
| Portal-Farbkonfiguration                       | #82   | `color_tokens` JSONB, Migration 0008, Color-Picker in Settings                        |
| Logo-Upload                                    | #82   | `POST /v1/portal/logo`, `GET /v1/portal/logo/file`, Upload-UI                         |
| Settings nur für Admins                        | #82   | Route-Guard in AppShell, Sidebar-Filter                                               |
| Schema-Import Hilfe                            | #82   | `<details>`-Hilfetext mit YAML-Beispiel im ImportModal                                |
| Markdown-Rendering StaticPageView              | #87   | `marked` + `DOMPurify`, `.prose`-CSS-Klasse (Closes #72)                              |
| OpenGraph- und Meta-Tags                       | #88   | `react-helmet-async`, alle 4 Detailseiten + StaticPageView (Closes #74)               |
| IIIF `link:alternate` im `<head>`              | #88   | `<link rel="alternate" type="application/ld+json">` auf ObjectDetailPage (Closes #75) |
| Karte auf PlaceDetailPage                      | —     | OSM-iframe mit Marker, graceful degradation (Closes #73)                              |
| Relation-Facetten beim Objekt-Browsing         | #89   | Denormalisierung in ES, 3 neue FacetPanel, URL-Filter (Closes #83)                    |

---

## Nächste Aufgaben (priorisiert)

### Priorität 1 — Offene Core-Issues

- ~~[#78](https://github.com/karkraeg/Katalon/issues/78) Relation-Type-Labels aus Vokabular auflösen~~ ✅
- ~~Admin-UI Authority-Autocomplete~~ ✅
- Snapshot-UI im Admin-Formular (Phase 7, Issue #217)
- Rate-Limiting auf öffentlichen Endpunkten (Phase 12, Issue #219)

### Priorität 2 — Deployment-Nacharbeit

- Nach nächstem Deployment: `POST /v1/search/reindex` aufrufen (Relation-Daten in bestehende ES-Dokumente einbetten)

### Priorität 3 — Langfristig

- ~~Batch-Medienimport (ZIP + CSV-Mapping, Issue #18)~~ ✅
- ~~IIIF-Viewer-Integration End-to-End (Issue #13)~~ ✅
- OAI-PMH ResumptionToken + Fehlerbehandlung (Issue #145)
- `system_fields` statt `__idno__` im Importer (Issue #194)
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
