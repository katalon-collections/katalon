# Changelog

All notable changes to Katalon are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), versioning: [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.21] - 2026-06-17

### Changed
- Elasticsearch index name is now configurable via `ES_INDEX_NAME` env var (default: `katalon_records`)

## [0.1.20] - 2026-06-17

### Fixed
- Admin: Subtyp-Wechsel im Neues-Formular lädt jetzt korrekte Felder nach — Felder anderer Subtypes werden ausgeblendet, eingegebene Werte bleiben im State erhalten

## [0.1.19] - 2026-06-17

### Fixed
- Portal: Verknüpfungen zeigen bei nicht-aufgelöstem Titel jetzt `[ID…]` statt irreführendem Typ-Label "Werk/Ereignis"

## [0.1.18] - 2026-06-15

### Fixed
- Portal: „Zugehörige Objekte" auf Occurrence-, Entity- und Place-Detailseiten zeigt jetzt Vorschaubilder (Primary Media wird per `media`-API geladen)

## [0.1.17] - 2026-06-15

### Fixed
- Portal: Entitäts-Links aus `RelationsList` nutzten `/entitys/` (Tippfehler) statt `/entities/` — Entitäts-Detailseiten waren nicht erreichbar
- Portal: Lange Textfelder (z. B. Beschreibung) aus `field_definitions` werden nun in der Hauptspalte mit Markdown-Rendering dargestellt statt als Rohtext in der schmalen Sidebar (gilt für Occurrence- und Entity-Detailseiten)

## [0.1.16] - 2026-06-15

### Fixed
- Admin: Beziehungen-Tab zeigt jetzt den echten Datensatz-Namen (z. B. "Electronic Arts") statt dem Fallback `idno` — Entitätsnamen aus `metadata.label` werden korrekt erkannt (spiegelt Backend-Logik `_extract_title`)

### Added
- Admin: Datensatz-Titel im Beziehungen-Tab ist jetzt anklickbar und navigiert direkt ins Bearbeitungsformular des verknüpften Eintrags

## [0.1.15] - 2026-06-15

### Fixed
- IIIF: `CANTALOUPE_BASE_URI` nutzt jetzt `${CANTALOUPE_PUBLIC_URL}` statt hartkodiertem `http://localhost/iiif` — verhindert falsche `http://`-URLs und doppelten `/iiif/iiif/`-Pfad in `info.json` hinter Reverse Proxy
- IIIF: Manifest-`id` und Canvas-IDs verwenden jetzt `katalon_base_url` statt `str(request.url)`, sodass auch hinter TLS-terminierenden Proxies `https://`-URLs erzeugt werden
- Nginx: `X-Forwarded-Proto`-Header wird jetzt an das Backend weitergeleitet (für `/v1/` und `/api/`)

## [0.1.14] - 2026-06-15

### Changed
- Feature-Flags für Feedback-Button umbenannt: `VITE_ADMIN_FEEDBACK_EMAIL` → `VITE_ADMIN_FEEDBACK_ENABLED`, `VITE_PORTAL_FEEDBACK_EMAIL` → `VITE_PORTAL_FEEDBACK_ENABLED` (Wert: beliebiger nicht-leerer String, z. B. `true`)

## [0.1.13] - 2026-06-15

### Added
- Portal: Feedback-Button — sendet über `/v1/feedback/public`-Endpoint (keine Auth erforderlich), aktivierbar via `VITE_PORTAL_FEEDBACK_ENABLED`
- Backend: neuer POST `/v1/feedback/public`-Endpoint ohne Authentifizierung für Portal-Nutzer

## [0.1.12] - 2026-06-15

### Changed
- Admin ScreenForm: Fehler-Banner listet jetzt die konkreten Fehlermeldungen aller ungültigen Felder auf

## [0.1.11] - 2026-06-15

### Fixed
- Admin ScreenForm: Pflichtfeld-Fehler bei `vocab`, `vocab_free`, `authority`, `relation`, `group`, `pid` und `richtext`-Feldern wurden nicht visuell angezeigt — Fehlermeldung erscheint jetzt einheitlich unter allen Feldtypen
- Admin ScreenForm: `console.log` bei Validierungsfehlern hinzugefügt für einfacheres Debugging

## [0.1.10] - 2026-06-15

### Fixed
- FeedbackButton: URL wurde durch `useMemo`-Cache immer mit dem Wert beim ersten Öffnen gesendet — URL, Zeit und Viewport werden jetzt direkt beim Absenden gelesen

## [0.1.9] - 2026-06-15

### Added
- Feedback-Endpoint `POST /v1/feedback`: sendet Feedback per Telegram-Bot (auth-geschützt, konfigurierbar via `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`)
- `docker-compose.traefik.yml`: Traefik-Integration als separates Overlay-File

### Changed
- Admin-Feedbackknopf: von `mailto:`-Link auf direkten API-Call umgestellt — sendet Nachricht inkl. URL, User, Viewport und Zeitpunkt
- `docker-compose.yml`: Telegram-Env-Vars ergänzt

## [0.1.8] - 2026-06-15

### Fixed
- Docker-Build reicht `VITE_ADMIN_FEEDBACK_EMAIL` an den Admin-Build durch

## [0.1.7] - 2026-06-15

### Added
- Admin-Feedbackknopf: optional per `VITE_ADMIN_FEEDBACK_EMAIL`, öffnet E-Mail mit Nachricht, URL und Browser-Kontext

## [0.1.6] - 2026-06-14

### Fixed
- nginx: `resolver 127.0.0.11 valid=10s` + variable `proxy_pass` — verhindert DNS-Caching-Bug nach Container-Rebuilds (falsche Upstream-IPs)

### Added
- Vokabular Deep Links: URL spiegelt aktives Vokabular wider (`#vocab/sprachen`), direkte Verlinkung und Browser-History funktionieren

## [0.1.5] - 2026-06-14

### Fixed
- OAI-PMH: `GetRecord` lieferte Draft-Datensätze aus — jetzt wird `status == "public"` geprüft, sonst `idDoesNotExist`
- OAI-PMH: `ListRecords`/`ListIdentifiers` ohne Set-Filter gaben alle Datensätze zurück — jetzt immer Baseline-Filter `status: public`
- Vocabulary-Import: CSV-Dateien in Windows-1252/Latin-1 (z.B. Excel-Export) erzeugten lautlos korrupte Umlaute — `_decode_csv()` probiert UTF-8, cp1252, latin-1 der Reihe nach
- Vokabular "Sprachen": Umlaute in Dänisch, Französisch, Isländisch, Niederländisch, Türkisch repariert

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
