# Changelog

All notable changes to Katalon are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), versioning: [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.5.11] - 2026-07-13

### Added
- Backup-Service konfigurierbar: `BACKUP_ENABLED` (an/aus) und `BACKUP_AT` (feste Uhrzeit `HH:MM` statt nur Intervall). Ist `BACKUP_AT` gesetzt, läuft das Backup täglich zur Uhrzeit (GNU-`date`-Zeitplan im Container); leer = Intervall-Modus wie bisher. Zeitzone über `TZ` steuerbar. (#273)

## [0.5.10] - 2026-07-13

### Added
- `backup`-Service im Compose-Stack (`docker/backup.sh`): täglicher `pg_dump` (gzip) + Media-`tar` mit Retention (`BACKUP_RETENTION_DAYS`, Default 14) und konfigurierbarem Intervall (`BACKUP_INTERVAL_SECONDS`). Ablage im Host-Verzeichnis `BACKUP_ROOT`. One-shot-Modus (`docker compose run --rm backup once`) für Ad-hoc-Backups vor Deploys. Nutzt dasselbe `postgis/postgis:16-3.4`-Image wie der DB-Server, damit `pg_dump`/`psql`-Minor-Versionen exakt passen. Restore-Drill dokumentiert und durchgespielt (`docs/04_produktion.md`) — Dump inkl. PostGIS-Extension sauber wiederhergestellt, Zeilenzahl verifiziert. (#273)

## [0.5.9] - 2026-07-13

### Changed
- `/health` prüft jetzt Datenbank und Elasticsearch aktiv und liefert HTTP 503 mit `{"status": "degraded", "checks": {...}}`, wenn eine Abhängigkeit nicht erreichbar ist. Vorher gab der Endpoint statisch `{"status": "ok"}` zurück, wodurch Load Balancer einen ausgefallenen Backend-Zustand nicht erkennen konnten. (Production-Readiness-Audit)

## [0.5.8] - 2026-07-10

### Fixed
- Importer-Probelauf berücksichtigt jetzt on-the-fly angelegte Felder: Der Dry-Run-Request sendet `fields_to_create` mit, das Backend merged sie als transiente Felddefinitionen. Fuzzy-Vokabular-Clustering, Typ- und Pflichtfeld-Validierung greifen dadurch schon in der Vorschau statt erst beim echten Import.

## [0.5.7] - 2026-07-09

### Added
- `.agents/knowledge/decisions/importer-fuzzy-vocab-clustering.md` — Decision-Doku zu Issue #269: rapidfuzz + Greedy-Clustering statt k-means, kanonischer Wert = häufigster Cluster-Wert, kein Silent-Merge.

## [0.5.6] - 2026-07-09

### Added
- Importer: Fuzzy-Clustering für Vokabular-Spalten im Probelauf (Levenshtein-Ähnlichkeit via `rapidfuzz`) erkennt Schreibweisen-Varianten (z. B. `Berlin`/`berlin`/`Brlin`) und schlägt einen kanonischen Wert vor. Bestätigung im UI übernimmt die Variante als `vocab_map`-Transform. (#269)

## [0.5.5] - 2026-07-09

### Added
- Dev-only OKF-Wissensbasis `.agents/knowledge/` (Decisions, Playbooks, Gotchas, Architecture, Glossary) mit lokalem Static-Site-Generator (`.agents/tools/okf_site.py`, `make knowledge-site`).
- `.agents/rules/backend.md` und `.agents/rules/frontend.md` — sprachspezifische Coding-Regeln, aus bestehenden Configs/Docs extrahiert.
- `AGENTS.md`: Lazy-Loading-Verdrahtung für Coding-Rules, Knowledge-Base und lebende Prozess-/Produktdokumente (`IMPLEMENTIERUNGSPLAN.md`, `DEV.md`, `KONZEPT.md`, `PRODUCT.md`, `DESIGN.md`).

## [0.5.4] - 2026-07-07

### Added
- Wikidata-User-Agent kann per `WIKIDATA_USER_AGENT` konfiguriert werden.

### Changed
- OAI-PMH ist als Protokoll-Endpunkt direkt unter `/oai` erreichbar statt unter `/v1/oai`.
- Dokumentation verweist auf die ausgelagerte Starlight-Dokumentationssite.

## [0.5.3] - 2026-07-07

### Changed
- Produkt- und Designkontext dokumentieren native Interaktion und sichtbaren Fokus als Accessibility-Grundlage.

### Fixed
- Portal-Karten, Suchtreffer, Vorschläge und Facetten verwenden native Links oder Buttons statt klickbarer `div`s.
- Portal und Admin erhalten sichtbare Tastatur-Fokuszustände, Suchlabels, Landmarken und Pagination-Semantik.
- Admin-Topbar-Suchergebnisse sind per Tastatur als Buttons erreichbar.

## [0.5.2] - 2026-07-06

### Fixed
- Backend-Unit- und Integration-Jobs setzen den verpflichtenden Testschlüssel für verschlüsselte Konfiguration, sodass Tests in GitHub Actions wieder gesammelt werden.
- Playwright-Workflow verwendet denselben nicht-geheimen Testschlüssel.

## [0.5.1] - 2026-07-06

### Added
- Produkt- und Designkontext dokumentieren Katalon als professionellen, responsiven kuratorischen Arbeitsplatz.
- Admin-E2E-Test deckt mobile Navigation bei 319 × 359 Pixeln ab.

### Changed
- Admin-Sidebar öffnet auf mobilen Viewports als bedienbarer Drawer; Topbar passt Navigation, Suche und Benutzeraktion an schmale Bildschirme an.
- Playwright startet die bestehende Compose-API und nutzt den Vite-Proxy statt einer zweiten, unvollständig konfigurierten Backend-Instanz.

### Fixed
- Login-Wechsel zur Admin-App verletzt nicht mehr die React-Hook-Reihenfolge.
- E2E-Tests warten zuverlässig auf den gespeicherten Login-Token und hängen nicht mehr von installationsspezifischen Schemafeldern oder einer defekten PNG-Fixture ab.

## [0.5.0] - 2026-07-06

### Added
- Vokabularterme nutzen jetzt die bestehende Schema-Engine für frei konfigurierbare Text-, Zahlen-, Boolean- und Authority-Felder.
- Vokabulare werden beim Anlegen unveränderlich als Term- oder Relationsvokabular klassifiziert; Schemafelder bieten nur passende Vokabulare an.

### Changed
- Normdaten an Vokabulartermen sind keine fest eingebaute Sonderstruktur mehr, sondern normale konfigurierte Authority-Felder.
- Vokabular-Felddefinitionen verwenden die stabile Vocabulary-UUID als Subtyp.
- Der spezielle Authority-CSV-Import wurde entfernt; normaler Term-, Label- und Hierarchieimport bleibt erhalten.

### Fixed
- Term-Metadaten werden serverseitig gegen Feldtyp, Pflichtstatus, Wiederholbarkeit und konfigurierte Authority-Quelle validiert.
- Bestehende Relationsvokabulare und das Systemvokabular `relation_types` werden bei der Migration korrekt klassifiziert.

## [0.4.1] - 2026-07-06

### Fixed
- Feedback-Button im Admin überlagerte die Editieren-Buttons nicht mehr: Trigger sitzt jetzt als Sidebar-Eintrag über der Versionsnummer, das Feedback-Panel öffnet unten links.

## [0.4.0] - 2026-07-06

### Added
- Vokabularterme können jetzt Normdaten tragen: strukturierte Verweise (GND, Geonames, Wikidata, Iconclass, VIAF, TGN) mit Autocomplete-Lookup im Term-Editor, mehrere pro Term. Neue `metadata`-JSONB-Spalte an `vocabulary_terms` hält die Verweise unter `authorities`.
- Vokabular-CSV-Import kann eine Normdaten-Spalte übernehmen: pro Import eine Quelle wählbar, Normdaten-ID-Spalte mappbar. Automatisches Label-Matching gibt es bewusst nicht — Normdaten-Verknüpfung bestätigt ein Mensch.

### Fixed
- Vokabular-Import verwarf zuvor gemappte `external_id`-Werte stillschweigend (keine Ziel-Spalte im Modell); Normdaten werden jetzt korrekt als `metadata.authorities` gespeichert.

## [0.3.6] - 2026-07-03

### Fixed
- `MEDIA_ROOT` in `docker-compose.prod.yml` wurde für `api`/`worker` fälschlich mit dem Host-Bind-Pfad aus `.env` überschrieben statt dem Container-internen Pfad `/var/lib/katalon/media`. Dadurch landeten hochgeladene Bilder im Container-Overlay statt im geteilten Media-Volume, sodass Cantaloupe sie nicht fand (404 bei der IIIF-Tile-Generierung) und Uploads dauerhaft im Status `error` hängen blieben.

## [0.3.5] - 2026-07-01

### Added
- Admin erneuert abgelaufene Sitzungen jetzt automatisch per Refresh-Token statt Benutzer nach 8 Stunden sofort auszuloggen.

### Changed
- Admin übernimmt den konfigurierten Institutionsnamen jetzt in Sidebar, Breadcrumbs und Browser-Tab; im Admin-Bereich wird der Tab als `<Institutionsname> Admin` benannt.

### Fixed
- Backend-`uv.lock` ist gegen inkonsistente `click-didyoumean`-Metadaten abgesichert; Backend-`uv`-Kommandos laufen damit wieder reproduzierbar.
- Projekthinweise dokumentieren jetzt explizit, dass Backend-Tests aus `backend/` gegen die richtige `.venv` laufen müssen.

## [0.3.4] - 2026-07-01

### Fixed
- `VITE_BASE_PATH=/admin/` in `Dockerfile.admin` wiederhergestellt — war in 0.3.3 versehentlich entfernt worden, was dazu führte dass die Admin-UI unter `/admin/` nicht lud (Assets wurden mit absolutem Pfad `/assets/` gebaut statt `/admin/assets/`).

## [0.3.3] - 2026-06-30

### Added
- KI-Unterstützung in Admin-Einstellungen und Formularen: Basis-URL, Modell, Token-Limits und verschlüsselt gespeicherter API-Key für Feldvorschläge.
- Formularfelder für Vokabulare, freie Vokabulare und Relationen zeigen Vorschläge direkt beim Fokussieren.

### Changed
- Entwürfe dürfen jetzt auch mit unvollständigen oder leeren Pflichtfeldern gespeichert werden; die Admin-UI zeigt dafür Validierungshinweise statt sofort hart zu blockieren.
- Docker-/Compose-Dokumentation und Dev-Setup beschreiben Rebuild-/Restart-Fälle klarer.

### Fixed
- `KATALON_SECRETS_KEY` wird an die relevanten Container durchgereicht und ist für Secret-Verschlüsselung verpflichtend.
- Backend startet nicht mehr ohne erreichbaren Cantaloupe-Service, damit Medien-Uploads nicht in einem halb defekten Stack landen.

### Breaking
- Installationen ohne gesetztes `KATALON_SECRETS_KEY` starten nicht mehr. `.env` und Deployment-Secrets müssen ergänzt werden.

## [0.3.2] - 2026-06-29

### Added
- Portal zeigt Gegenrichtungslabels jetzt auch in den Inline-Objektkarten auf Orts-, Entitäts- und Occurrence-Detailseiten.
- Backend legt `relation_types` automatisch an und übernimmt vorhandene Relationscodes als bearbeitbare Terme.

### Fixed
- Schema-abgeleitete Relationen berücksichtigen nur echte Top-Level-Relationsfelder; Gruppen-Subfelder werden nicht doppelt als Top-Level behandelt.
- Medien-Uploads bleiben in der Admin-UI sichtbar, selbst wenn nachgelagertes Speichern von Lizenz/Rechteinhaber fehlschlägt.
- Rechteinhaber-Felder in der Medienkarte senden beim Blur jetzt konsistente Werte ohne Lost-Update zwischen Name und URI.
- Validierungsfehler für Relations-Subfelder in Gruppen nennen den betroffenen Eintrag explizit.

## [0.3.1] - 2026-06-29

### Added
- Containerfelder unterstützen Relationen zu Objekten, Entitäten, Orten und Ereignissen.
- Mediendateien speichern optionale Lizenz- und Rechteinhaber-Angaben.
- Schemafelder können Standardwerte erhalten und für Nicht-Administratoren gesperrt werden.

## [0.3.0] - 2026-06-27

### Added
- Import-Status-Banner: läuft ein Import, erscheint auf allen Screens ein Banner mit Fortschritt, Ergebnis und Abbrechen-Button. Überlebt Tab-Close / Navigation.
- Import abbrechen: Abbrechen-Button setzt Redis-Flag; Worker bricht nach max. 10 Zeilen sauber ab und meldet bereits erstellte Datensätze.
- Probelauf-Button zeigt Spinner während Prüfung läuft.
- Probelauf-Fehlertabelle gruppiert Fehler nach Meldung (statt 80k Einzelzeilen im DOM).
- Pflichtfelder blockieren Import nicht mehr — nur noch Warnung (amber), Datensätze werden als Draft angelegt.
- nginx.admin.conf: `resolver 127.0.0.11` + Variable-Upstream verhindert 502 nach API-Rebuild.


## [0.2.9] - 2026-06-27

### Fixed
- Upload-Limit für Importer erhöht: nginx.admin.conf fehlte `client_max_body_size`, Standard-Limit von 1 MB blockierte Dateien > 1 MB.

### Changed
- Importer: Zeilen werden nach dem Upload in Redis gespeichert (1h TTL). Dry-Run und Import nutzen `upload_id` statt alle Zeilen als JSON hin- und herzuschicken. Zeilenlimit (vorher 10.000) entfällt.


## [0.2.8] - 2026-06-26

### Fixed
- Beziehungen-Panel zeigt jetzt `inverse_label` (Gegenrichtung) wenn der aktuelle Record das Ziel der Relation ist, statt immer das Forward-Label.

## [0.2.7] - 2026-06-26

### Changed
- Beziehungen-Panel ist jetzt read-only Navigationsansicht; alle Relationen werden als klickbare Links angezeigt. Anlegen von Relationen ausschließlich über Schema-Felder im Metadaten-Formular (closes #240).

### Removed
- Generisches „Hinzufügen" im Beziehungen-Panel entfernt (inkl. Add/Edit-Formular und Edit/Delete-Buttons pro Relation).

## [0.2.6] - 2026-06-26

### Changed
- Implementierungsplan aktualisiert Phase 14/Vorgänge und robuste ES-Indexierung als erledigt.
- Robuste ES-Indexierung, Reindex, Health und Reconciliation berücksichtigen jetzt auch Vorgänge.

### Fixed
- Admin-Formular zeigt „Neuer Vorgang" und weitere neue Datensatz-Titel grammatikalisch korrekt.
- Admin-Löschdialog nutzt echte Singular-Labels statt abgeschnittener Pluralformen.
- Vorgang-Abschluss reindiziert geänderte Objekte, damit `collection_status` in Elasticsearch aktuell bleibt.

## [0.2.5] - 2026-06-26

### Added
- Objektformular hat eigenes Panel „Vorgänge" für feste Objekt-Vorgang-Verknüpfungen

### Fixed
- Vorgangsschemata laden mit eingebauten Vorgangstypen wie `conservation`

## [0.2.4] - 2026-06-26

### Added
- Vorgangsformular hat eigenes Panel „Objekte im Vorgang" mit Objektstatus und schnellem Objekt-Hinzufügen

## [0.2.3] - 2026-06-26

### Added
- Vorgangsliste hat Schnellfilter für überfällige aktive Vorgänge
- Vorgangsdokumentation beschreibt API-Endpunkte, Portal-Sichtbarkeit und Reindex-Schritt für `collection_status`

### Changed
- Vorgang-Abschluss nutzt einen klaren Dialog mit Statuswechsel/ohne Statuswechsel statt Browser-Confirm
- Vorgangsformular benennt Objektverknüpfungen sichtbarer als „Objekte & Beziehungen"

## [0.2.2] - 2026-06-26

### Added
- Admin-Vorgangsliste filtert nach Vorgangstyp, Fälligkeit bis und Referenznummer
- Elasticsearch-Index enthält `collection_status` für Objekte

### Changed
- Anonyme Suche blendet nicht aktive Objekte aus, ohne andere Record-Typen zu verstecken
- Vorgang-Abschluss nutzt Bestätigungsdialog statt freier Prompt-Eingabe für vorgeschlagenen Sammlungsstatus

## [0.2.1] - 2026-06-26

### Added
- Admin-Objektformular zeigt und speichert `collection_status` als Systemfeld

### Changed
- Öffentliche Objektlisten und Objektdetails zeigen anonym nur noch Objekte mit aktivem Sammlungsstatus

## [0.2.0] - 2026-06-26

### Added
- Procedure/Vorgänge als fünfter interner Record-Typ mit CRUD-API, Migration, Admin-Liste/Formular, Audit Log, Snapshots und Schema-Feldern
- `collection_status` auf Objekten als Systemfeld für Sammlungsstatus
- Validierung gegen zweite aktive ausgehende Leihgabe (`loan_out`) für dasselbe Objekt
- Abschluss-Workflow für Vorgänge kann verknüpfte Objekt-Sammlungsstatus in einer Transaktion setzen
- Konzeptpapier `docs/konzept-vorgaenge.md`

### Changed
- Ruff ignoriert historische Zeilenlängen (`E501`); echte `E/W/F/I/UP`-Regeln laufen backendweit grün

## [0.1.22] - 2026-06-18

### Added
- Relationstypen unterstützen jetzt ein `inverse_label` (Gegenrichtungslabel): In der Detailansicht wird das Label richtungsabhängig angezeigt – wenn die aktuelle Seite das *Ziel* einer Relation ist, erscheint das Gegenrichtungslabel statt des Hinrichtungslabels
- Admin Vokabular-Editor: neues Feld „Gegenrichtung DE" bei Term anlegen/bearbeiten sowie neue CSV-Import-Targets `inverse_label:de` / `inverse_label:en`
- DB-Migration `a1b2c3d4e5f6`: Spalte `inverse_label JSONB` in `vocabulary_terms`

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
