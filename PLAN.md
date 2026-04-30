# Katalon – Fortschrittsplan

> Letzte Aktualisierung: 2026-04-30

## Implementierungsstatus

| Phase | Beschreibung                                                      | Status                                                                                  |
|-------|-------------------------------------------------------------------|-----------------------------------------------------------------------------------------|
| 0     | Infra (Docker Compose, Dockerfiles, pyproject.toml, config, main) | ✅ Fertig                                                                                |
| 1     | Core-DB (ORM-Models, Alembic-Init + erste Migration)              | ✅ Fertig                                                                                |
| 2     | Schema-Engine (field_definitions, Vokabulare)                     | ✅ Fertig                                                                                |
| 3     | CRUD alle 4 Typen + Relationen                                    | ✅ Fertig (alle 4 Typen + Relationen)                                                    |
| 4     | Auth (JWT, Rollen) + Audit Log                                    | ✅ Fertig                                                                                |
| 5     | Media & IIIF (Upload, Celery, Cantaloupe)                         | ✅ Grundgerüst fertig                                                                    |
| 6     | Admin-UI (React + TypeScript, alle 6 Screens)                     | ✅ Fertig                                                                                |
| 7     | Elasticsearch + Versionierung (Snapshots)                         | ✅ Fertig (ES-Client, Search-Service, Celery-Reindex, GET /v1/search)                    |
| 8     | Public-Portal (React) + Theme-System (Drop-in Bundles)            | ✅ Fertig (Homepage, Suche, Detail, Theme-aware)                                         |
| 9     | Authority-Plugin-System (GND, Geonames)                           | ✅ Fertig (ABC, GND/Geonames-Adapter, /v1/authority/search+fetch)                        |
| 10    | Smart Importer (Excel/CSV ETL)                                    | ✅ Fertig (CSV-Parse, Mapping, Dry-Run, Celery-Import, /v1/importer)                     |
| 11    | OAI-PMH                                                           | ✅ Fertig (Identify, ListRecords, GetRecord, ListSets, ListMetadataFormats, Dublin Core) |
| 12    | Hardening (Rate Limiting, Performance)                            | ✅ Fertig (slowapi 200 req/min, Unit-Tests health+importer+oai)                          |

---

## Admin-UI Design

Das Admin-UI folgt dem Design-Prototypen aus `design-prompts/02_admin_ui.md`.

### Design-Tokens

- **Fonts:** IBM Plex Sans (UI) + IBM Plex Mono (Monospace)
- **Sidebar:** Dark Navy `#0b1a33`, 236px breit
- **Akzent:** Navy Blue `#1e3a8a`
- **Hintergrund:** `#f4f5f7` (App), `#fff` (Panels)
- **Status-Badges:** Draft (grau), Intern (orange), Öffentlich (grün)

### 6 Screens

1. **Listen-Ansicht** (`/objects`, `/entities`, `/places`, `/occurrences`) — Tabelle mit Suche, Filter, Bulk-Aktionen
2. **Erfassungsformular** (`/objects/new`, `/objects/:id`) — Dynamisches Formular aus field_definitions
3. **Schema-Editor** (`/schema`) — Felder per Typ definieren
4. **Vokabular-Verwaltung** (`/vocabularies`) — Terme und Baum-Hierarchien
5. **Importer** (`/import`) — 4-Schritt-Wizard Upload → Mapping → Dry Run → Import
6. **Audit Log** (`/audit`) — Filterbarer Änderungs-Feed

---

## Branch-Strategie

- `main` — stabile Releases
- `claude/implement-katalon-admin-design-unUkN` — aktiver Entwicklungsbranch

---

## Theme-System Discovery-Portal (Post-MVP)

Das Public-Portal wird vollständig themebar via Drop-in Bundle. Kein Rebuild nötig.

**Ablauf:**

1. Theme-Verzeichnis nach `/var/lib/katalon/themes/<name>/` legen
2. `PORTAL_THEME=<name>` in `.env` setzen
3. `docker compose restart portal`

**Bundle-Inhalt:** `theme.json` (CSS-Tokens, Fonts, Logo-Pfade) + `custom.css` + Assets.

Vollständiges Konzept → `KONZEPT.md` Abschnitt 11.

---

## Offene Entscheidungen

- [ ] React-Router v6 für Admin-UI
- [ ] TanStack Query für API-State-Management
- [ ] OpenAPI-Codegen für TypeScript-Client (nach Phase 3)
- [ ] Fuzzy-Datum UI-Komponente: Präzisions-Selektor (Jahr/Monat/Tag + „ca.")
- [ ] Theme-Loader: SSR-inject vs. client-side (kein Flash-of-unstyled-content)

---

## Offene Aufgaben (aus README)

Diese Aufgaben wurden in der `README.md` als noch offen markiert. Sie sind priorisiert nach kurzfristiger Wirkung für Demos und Präsentationen.

### Priorität 1 — Admin-Workflows

- Schemata: Neues Feld anlegen, Feld bearbeiten, löschen und Sortierung persistent machen (aktuell mock-basiert).
- Objekte: Objekt-CRUD an die echte API anbinden (Erstellen, Aktualisieren, Löschen, Statuswechsel, Audit-Log schreiben).
- Vokabular: Neuer Term anlegen / editieren / löschen und hierarchische Beziehungen speichern.
- Bilderupload: Endpunkt + Celery-Processing + Cantaloupe-Manifest-Verknüpfung End-to-End herstellen.
- Suche im Admin-Panel: Topbar/Sidebar-Suchen mit API-Integration (nicht nur lokal filtern).

### Priorität 2 — Präsentationsoberfläche (Portal)

- Public-Portal: Startseite, Suche, Detailansicht so fertigstellen, dass sie für Demos nutzbar ist.
- IIIF-Viewer: Objekt-Detail mit echten Manifests und Kacheln verbinden.
- Theme-Demo: Beispiel-Theme bereitstellen und Theme-Wechsel demonstrieren.

### Priorität 3 — Ergänzungen

- Fehler- und Ladezustände in UI-Screens verbessern.
- CRUD für Entitäten, Orte und Occurrences im Admin nachziehen.

### Vorschlag für Agentenreihenfolge

1. Schema-Editor + Vokabular-CRUD an API anbinden.
2. Objekt-CRUD + Medienupload implementieren.
3. Globale Suche im Admin an den Search-Service anbinden.
4. Public-Portal mit IIIF und Theme-Demo ausstatten.
5. Restliche Typen (Entity, Place, Occurrence) im Admin ergänzen.
