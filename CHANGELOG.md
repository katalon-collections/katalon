# Changelog

All notable changes to Katalon are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), versioning: [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.4] - 2026-06-14

### Fixed
- ScreenList: Einzelne (nicht-repeatable) `vocab`-Felder zeigten `[object Object]` — jetzt wird korrekt `label` angezeigt

## [0.1.3] - 2026-06-14

### Fixed
- docker-compose.yml: alle Credentials und Konfigurationswerte nutzen jetzt `${VAR}`-Substitution aus `.env` (kein Hardcoding mehr)
- DB-Healthcheck referenziert jetzt `${POSTGRES_USER}` statt hartem Wert

### Added
- AGENTS.md: Regel "Datensicherheit – ABSOLUTE VERBOTE" — DB-Volumes niemals ohne explizite Bestätigung löschen

## [0.1.2] - 2026-06-14

### Fixed
- Login error now shows "Falsche E-Mail oder Passwort." instead of "Sitzung abgelaufen"

### Added
- README: first-run credentials documented

## [0.1.1] - 2026-06-14

### Added
- Semantic versioning rule in AGENTS.md — patch bump on every commit
- Version number displayed in admin sidebar (bottom left)

### Fixed
- List view: `[object Object]` for vocab-strict and relation fields in table columns
- List view: action column (Edit/Delete) sticky-right, always visible on wide tables

## [0.1.0] - 2026-06-14

Initial release for internal testing.

### Added
- CRUD for all 4 primary types: Objects, Entities, Places, Occurrences
- Dynamic schema engine with configurable field definitions
- Container fields (nested metadata groups)
- Vocabulary management (strict and free-text)
- JWT authentication with roles (admin, editor, viewer)
- Audit log for all write operations
- Record snapshots / versioning
- Relation management with metadata and inline editing
- Media upload with IIIF tile generation via Cantaloupe
- Elasticsearch full-text search and faceted browsing
- Public portal with detail pages and IIIF viewer (Clover)
- Authority adapter system: GND, VIAF, Wikidata, Geonames, Getty TGN, ICONCLASS
- Import wizard: CSV, TSV, Excel, XML with dry run and progress
- Batch media import (ZIP + mapping)
- OAI-PMH endpoint with Dublin Core export
- Generic metadata mappings for export formats
- Rate limiting on public endpoints
- Production secrets guard at startup
- Cantaloupe health-check at startup
- Robust ES indexing: retry, cascade reindex, reconciliation job, index health dashboard
- User management (admin UI)
- Subtype configuration

### Fixed
- List view: `[object Object]` display for vocab-strict and relation fields
- List view: action column (Edit/Delete) now sticky-right, visible on wide tables
