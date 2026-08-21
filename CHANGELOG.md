# Changelog

All notable changes to Katalon are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), versioning: [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.3.2] - 2026-08-21

### Fixed
- Portal-Detailseiten: `useFieldDefinitions` lieferte Schema-Felder asynchron nach dem Datensatz, wodurch das neue detail_slot/detail_role-Layout kurz falsch (bzw. fälschlich als „metadata only") gerendert wurde, bevor es auf das korrekte Layout sprang. Detailseiten warten jetzt auch auf das Schema, bevor sie rendern.
- Admin-Schema-Editor: Die Checkbox-Zeile für Feldeigenschaften hatte kein Umbruchverhalten und lief bei den zwei neuen Detailseiten-Layout-Dropdowns Gefahr, in schmaleren Fenstern über den Rand hinauszulaufen. Zeile umbricht jetzt (`flex-wrap`), die beiden neuen Dropdowns stehen zudem in einer eigenen Zeile statt zwischen den Checkboxen.

## [1.3.1] - 2026-08-21

### Fixed
- Portal-Detailseiten-Layout: Beim Umschalten der Sidebar-Position (links/rechts) wurden bisher auch die Spaltenbreiten vertauscht, sodass die Metadaten-Spalte plötzlich breiter als der Hauptbereich war. Die Seitenspalte bleibt jetzt unabhängig von der Position immer die schmale Spalte.
- Portal-Detailseiten-Layout: Records ganz ohne Hauptbereichs-Inhalt (keine Medien, keine Beschreibung, keine Hauptbereichs-Felder, keine Beziehungen) zeigten eine leere breite Spalte neben der schmalen Seitenspalte. Layout klappt in diesem Fall jetzt auf eine einzelne, breitenbegrenzte Spalte zusammen.

## [1.3.0] - 2026-08-21

### Added
- Konfigurierbare Portal-Detailseiten-Layouts: pro Feld steuerbar, ob es im Hauptbereich oder in der Seitenspalte erscheint (`detail_slot`) und ob es die Beschreibungsrolle übernimmt (`detail_role`), plus ein globaler Schalter für die Sidebar-Position (links/rechts) in den Portal-Einstellungen. Siehe Issue [#317](https://github.com/karkraeg/Katalon/issues/317).
- Portal: gemeinsamer `DetailPageLayout`-Baustein für Objekte/Entitäten/Orte/Occurrences ersetzt die bisherige, pro Seite duplizierte und teils heuristische (Textlänge-basierte) Platzierungslogik.

## [1.2.18] - 2026-08-20

### Fixed
- Docs: `docs/04_produktion.md` Option C korrigiert — für Reverse-Proxy-Deployments (Traefik, …) wird kein Self-signed-Zertifikat für Prod mehr empfohlen (`make certs` ist nur für lokale Entwicklung gedacht), sondern eine eigene nginx-Config ohne `listen 443 ssl`-Block.

## [1.2.17] - 2026-08-20

### Fixed
- Docs: `docs/04_produktion.md` beschreibt jetzt explizit den Fall, dass `nginx` hinter einem TLS-terminierenden Reverse Proxy (z. B. Traefik) läuft — der `listen 443 ssl`-Block verlangt trotzdem ladbare Zertifikate unter `docker/certs/`, auch wenn Port 443 nie extern erreichbar ist. Ohne Zertifikate startet nginx nicht (`cannot load certificate ... BIO_new_file() failed`).

## [1.2.16] - 2026-08-20

### Fixed
- Portal: Bildvorschauen verwenden IIIF-JPEG-Derivate statt browser-inkompatibler TIFF-Rohdateien. Dadurch erscheinen TIFF-, JPEG-, PNG- und WebP-Bilder einheitlich in Listen, Karten, Medienleiste und Detail-Fallback.

## [1.2.15] - 2026-08-20

### Added
- Schema-Verwaltung: Felder und Gruppen-Subfelder können als intern markiert werden. Solche Werte bleiben für angemeldete Mitarbeitende sichtbar, werden aber nicht über anonyme REST-, Portal-, Such-, OAI- oder IIIF-Ausgaben veröffentlicht.

### Changed
- Docker-Backend-Builds verwenden gepinntes `uv` mit BuildKit-Cache statt `pip install uv`; bereits geladene Python-Abhängigkeiten werden bei Paketversionsänderungen wiederverwendet.
- Cantaloupe rendert JPEGs mit Java2D statt TurboJPEG, damit IIIF-Bildantworten nicht leer bleiben.

## [1.2.13] - 2026-08-20

### Fixed
- Portal: Doppelte Thumbnails bei Bild-Objekten entfernt – MediaThumb-Leiste unter IIIF-Viewer wird nur noch bei gemischten Medien (Bild+Nicht-Bild) angezeigt.

## [1.2.12] - 2026-08-20

### Added
- Portal: Admins können für Objekte, Entitäten, Orte und Ereignisse einzeln festlegen, ob ein Browsing-Menüpunkt erscheint. Deaktivierte Typen bleiben über direkte Links zugänglich.

## [1.2.11] - 2026-08-20

### Added
- Repo-Root als uv-Workspace (`pyproject.toml` mit `members = ["backend"]`): `uv run katalon-manage` und `uv run pytest` direkt aus dem Root nutzbar.
- `katalon-manage`-Launcher (`katalon.management.runner`): fehlender/zu kurzer `KATALON_SECRETS_KEY` meldet eine einzelne lesbare Zeile auf stderr statt eines Pydantic-Stacktraces.

### Changed
- `Settings` löst `.env` source-relativ auf (`backend/.env` und Root-`.env`), unabhängig vom Arbeitsverzeichnis.

## [1.2.10] - 2026-08-20

### Added
- Management-CLI `katalon-manage` für Dev/Ops im Backend:
  - `db-reset`: Daten-Tabellen zurücksetzen, Konfiguration-Tabellen optional mit `--all` ebenfalls, automatisches `pg_dump`-Backup vor dem Reset (außer `--no-backup`), interaktive Bestätigung (außer `--yes`).
  - `import-csv` / `import-xml`: Datensatz-Import aus der Kommandozeile mit JSON-Mapping-Datei, `--dry-run`, `--subtype`, `--idno-strategy`, `--upsert-strategy`, `--auto-publish` und `--media-selector`.
  - `reset-admin`: Bestehendes Admin-Passwort-Reset ist auch über `katalon-manage reset-admin` erreichbar; `katalon-reset-admin` bleibt erhalten.

### Added
- Medienzuordnung aus dem Metadatenimport: Eine wählbare Datei-Spalte bzw. ein XML-Element speichert offene Medienreferenzen je Objekt; spätere Ordner- oder ZIP-Uploads ordnen Bilder ohne separate CSV automatisch und konfliktgesichert zu.

## [1.2.8] - 2026-08-20

### Fixed
- Admin › Einstellungen › Facetten: Das Speichern persistiert jetzt korrekt. Direkte Facetten werden als `is_facet` auf der jeweiligen `FieldDefinition` gesetzt (das Backend verwendet dies als Quelle der Wahrheit und reindexiert automatisch); vererbte Facetten bleiben in `portal_config.facet_fields` gespeichert.

## [1.2.7] - 2026-08-20

### Fixed
- Portal: Detailseiten und Startseite zeigen jetzt lesbare Labels (z. B. Objekt-`label`-Feld) statt UUID-basierter Inventarnummern als Titel. Wiederholbare/übersetzbare Feldwerte werden über `recordTitle()` korrekt aufgelöst.

## [1.2.6] - 2026-08-20

### Added
- Import (XML): Mehrdatei-Upload für XML (z. B. LIDO-Exports mit einer Datei pro Datensatz) — Dateien werden serverseitig zu einem synthetischen Batch-Dokument zusammengeführt und wie gewohnt per Record-Element gemappt.
- Mapping-UI: Selektoren werden nach übergeordnetem Element gruppiert angezeigt; kontextabhängige Beschriftungen (XML vs. CSV/Excel) für ID-Strategie und Feldauswahl.

### Fixed
- Import (XML, Mehrdatei-Upload): Namespace-Präfixe wurden anhand des synthetischen Batch-Root-Elements statt des jeweiligen Quell-Roots aufgelöst und dadurch als volle URIs statt lesbarer Präfixe angezeigt.
- Mapping-UI: lange XML/LIDO-Selektorpfade wurden ohne Kürzung dargestellt und liefen aus dem UI heraus.

## [1.2.5] - 2026-08-20

### Changed
- Dev-Workflow: Celery-Worker im Docker-Dev-Stack lädt Code-Änderungen jetzt automatisch (`watchfiles`) statt manuellen Container-Neustart zu erfordern.
- `Makefile`: neue Kurzbefehle `make dev`, `make test`, `make migrate`, `make certs` (self-signed TLS-Zertifikat für lokales HTTPS).
- Nginx/Compose: äußerer nginx unterstützt jetzt HTTPS (Port 443) über selbst-signiertes Dev-Zertifikat; API-Port 8000 im normalen Compose-Stack nicht mehr nach außen exponiert (nur noch intern über nginx erreichbar).

## [1.2.4] - 2026-08-20

### Fixed
- Import (XML): Import-Lauf schlug mit `'list' object has no attribute 'strip'` fehl, sobald ein wiederholtes XML-Element auf ein nicht-wiederholbares Feld gemappt wurde. `apply_mapping()` normalisiert Selector-Werte jetzt einheitlich über `_row_values()`.

## [1.2.3] - 2026-08-19

### Changed
- Audit-Log (Admin, Datensatz-Detailseite): Update-Einträge zeigen jetzt geänderte Felder mit alt/neu-Werten statt nur Aktion und Nutzer.

## [1.2.2] - 2026-08-19

### Changed
- Audit-Log (Admin): KI-Schema-Assistent-Einträge zeigen jetzt Aktionsbezeichnung, betroffenen Datensatztyp/-subtyp, Modell und Token-Anzahl statt der rohen Aktion `ai_schema_assist` und einer gehashten Schema-ID.

## [1.2.1] - 2026-08-19

### Fixed
- Datumsfeld (Admin): Jahre unter 1000 (z. B. `100`) wurden nicht auf 4 Stellen gepadded und dadurch als ungültig zurückgewiesen — betraf auch Zeitraum-Eingaben wie `vor 100`.

## [1.2.0] - 2026-08-19

### Added
- KI-Assistent für Felder (Admin): fragt bei unzureichenden Angaben gezielt nach statt zu raten; erklärt Normdaten-Hinweise (authority-Felder gehören an den verknüpften Datensatz — Ort/Person —, nicht ans Objekt); modelliert Personen/Firmen als Relation auf `entity`, Ereignisse/Werke als Relation auf `occurrence`, Orte als Relation auf `place`; nutzt für Zeiträume/Unschärfe das date-Feld (EDTF-lite) statt von/bis-Gruppen; schlägt kein Titel-Feld vor (Systemfeld `label` übernimmt); orientiert Vorschläge an den DDB-Erfassungsfeldern. Vorschläge: einzelne Felder vor dem Übernehmen abwählbar, ungenutzte Vokabulare werden übersprungen, URLs im Chat klickbar.
- Schema-Verwaltung: Soft-gelöschte Felder werden beim erneuten Anlegen gleichen Namens automatisch reaktiviert (gleiche ID, Historie bleibt erhalten); doppelter Feldname liefert 409 statt 500.

## [1.1.2] - 2026-08-19

### Added
- Datumsfelder unterstützen Zeiträume und Unschärfe (EDTF-lite): Eingabe per Freitext wie `ca. 1900`, `um 1900`, `1900 (unsicher)`/`1900?`, `1900 bis 1950`, `vor 1900`, `nach 1900` — wird intern kanonisch als `1900~`, `1900?`, `1900/1950`, `/1900`, `1900/` gespeichert. Backend-Validierung, Admin-Formular-Parser und Portal-Anzeige (formatiert kanonische Werte zurück in Lesetext) angepasst.

## [1.1.1] - 2026-08-19

### Added
- Datumsfelder unterstützen v. Chr.-Jahre (BCE): ISO-Schreibweise mit führendem Minus und vierstelligem Jahr (z. B. `-0043` = 44 v. Chr.), inkl. proleptisch-gregorianischer Schaltjahresregel (Jahr 0 = 1 v. Chr.) — Backend-Validierung und Admin-Formular (Normalisierung `TT.MM.JJJJ`).

### Changed
- `docs/01_datenmodell.md` und `docs/02_schema_verwaltung.md`: Datumsformate um BCE/Jahresangaben erweitert.

## [1.1.0] - 2026-08-19

### Added
- KI-Assistent für die Schema-Verwaltung (Admin): Schema-Vorschläge und Felddefinitionen per Chat mit konfigurierbarem OpenAI-kompatiblem Provider generieren (Einstellungen → KI; Endpoint `/api/v1/admin/schema/ai-chat`).
- Admin-Einstellungen: KI-Verbindungstest (`/api/v1/admin/ai-check`) und Setzen/Entfernen des KI-API-Keys als Secret.

## [1.0.8] - 2026-08-19

### Changed
- Backend-Typisierung: `mypy --strict` läuft jetzt fehlerfrei über die gesamte Codebasis (`src/katalon`). Dabei behoben: defekter OAI-PMH-GetRecord-Pfad (veralteter Elasticsearch-`ignore`-Parameter, der zur Laufzeit eine Exception warf), FastAPI-Startup-Crash durch `Annotated`-`Depends`-Kombination in Auth-Dependencies sowie diverse fehlende/inkorrekte Typannotationen.
- Dev-Dependencies: `celery-types`, `types-PyYAML`, `types-aiofiles` für mypy ergänzt; `pydantic.mypy`-Plugin aktiviert.

## [1.0.7] - 2026-08-19

### Fixed
- Admin mobile UI hardening:
  - Audit-Log: diff values that are objects/arrays are now rendered as JSON strings instead of `[object Object]`; timeline stacks vertically on narrow viewports.
  - Banner screen: page header, two-column form and banner list rows now stack on mobile.
  - Einstellungen: sidebar navigation becomes a horizontal scrollable strip above the content on small screens.
  - Benutzer: table cells wrap, action buttons stack, and the table gets a horizontal scroll fallback on narrow screens.
  - Global search placeholder shortened so it no longer clips in the compact topbar.

## [1.0.6] - 2026-08-18

### Added
- Produktions-Frontend-Builds setzen `VITE_API_URL`/`VITE_PORTAL_URL` über `.env` (via `docker-compose.prod.yml` und Docker-Build-Args), damit absolute URLs korrekt in Admin/Portal-Images eingebettet werden.
- Performance-Tests mit Locust: `backend/tests/performance/locustfile.py` plus README; Szenarien für öffentliches Portal und authentifizierte Admin-API.
- Statisches OpenAPI-Schema im Repository-Root (`openapi.json`) und Generator-Skript `scripts/gen_openapi.py`.
- Neue Doku-Seite `docs/15_api_dokumentation.md` für Swagger/ReDoc/OpenAPI-Schema.

### Changed
- `docker/nginx.prod.conf`: Moderne TLS-Cipher-Suite (Mozilla Intermediate) und `ssl_prefer_server_ciphers off` hinterlegt.
- `docs/04_produktion.md` auf `.env`-basierte VITE-Build-Argumente und das tatsächlich verwendete Zertifikats-Verzeichnis-Mount aktualisiert.

## [1.0.5] - 2026-08-18

### Added
- Soft-Delete für Objects/Entities/Places/Occurrences: Löschen setzt `deleted_at` statt Hard-Delete, Relationen bleiben erhalten. Neue Endpoints `POST /{type}/{id}/restore` und `GET /{type}/trash/list` (admin/superuser).
- Konfigurierbare Purge-Retention (`purge_after_days`, Default 30) und täglicher Celery-Purge-Job: hard-deleted Records nach Ablauf der Frist inkl. Medien-Dateien auf Disk.
- Anonyme Portal-Zugriffe auf soft-deleted, ehemals öffentliche Records liefern jetzt `410 Gone` (Tombstone-Signal) statt `404`.
- Vorgänge (Procedures) bekommen `POST /{id}/archive` (Status-Flip auf `archived`) statt Soft-Delete – kein Portal-Auftritt, daher kein Tombstone nötig.
- Migration `0037`: `deleted_at` auf `objects`, `entities`, `places`, `occurrences`.

### Fixed
- ES-Reconciliation-Job, Bulk-Reindex und Full-Reindex ignorierten `deleted_at` und hätten soft-deleted Records beim nächsten Lauf wieder in den Suchindex aufgenommen. Alle drei filtern jetzt korrekt.
- IIIF-Manifest-Endpoint und Portal-Relationen-Liste prüften nur `status`, nicht `deleted_at` – beides jetzt konsistent mit dem Tombstone-Verhalten.

## [1.0.4] - 2026-08-18

### Fixed
- Backend: Audit-Log-Einträge für "Gelöscht" zeigten statt Titel/ID-Nr. eine gekürzte UUID, weil das Label zur Anzeigezeit aus dem (bereits gelöschten) Datensatz nachgeladen wurde. `idno`/Titel werden jetzt beim Löschen selbst in `changed_fields` gesichert (Objekt, Entity, Place, Occurrence, Procedure) und beim Rendern des Log-Eintrags bevorzugt verwendet.
- Admin: Objekt-/Entity-/Place-/Occurrence-/Vorgangs-Liste entfernte eine gelöschte Zeile erst nach dem Neuladen der Seite sichtbar, wenn der Re-Fetch nach dem Löschen langsamer war als der Confirm-Dialog. Die Zeile wird jetzt sofort optimistisch aus der lokalen Liste entfernt.

## [1.0.3] - 2026-08-18

### Fixed
- Backend: derselbe Bug wie bei Objekten (siehe 1.0.2) betraf latent auch Vokabulare mit Termen – `Vocabulary.terms` hatte ebenfalls keine `cascade`/`passive_deletes`-Konfiguration, sodass ein Löschen der Vokabular-Zeile `vocabulary_terms.vocabulary_id` auf `NULL` gesetzt hätte. Aktuell gibt es zwar noch keinen Lösch-Endpunkt für ganze Vokabulare, aber die Modellkonfiguration ist jetzt konsistent mit dem DB-seitigen `ON DELETE CASCADE`.

### Added
- Backend: Integrationstest deckt jetzt ab, dass das Löschen eines Objekts mit angehängten Mediendateien tatsächlich (gegen eine echte Postgres-DB) durchläuft, statt das nur über Mocks zu simulieren – genau die Lücke, durch die der 1.0.2-Bug unbemerkt blieb.

## [1.0.2] - 2026-08-18

### Fixed
- Backend: Löschen eines Objekts mit angehängten Mediendateien schlug mit Internal Server Error fehl (500), sobald `force=true` verwendet wurde – SQLAlchemy versuchte beim Löschen des Objekts `media_files.object_id` auf `NULL` zu setzen statt die Zeilen per DB-seitigem `ON DELETE CASCADE` mitzulöschen, was an der `NOT NULL`-Constraint scheiterte. `Object.media_files` hat jetzt `cascade="all, delete-orphan"` und `passive_deletes=True`.

### Added
- Audit-Log erfasst jetzt auch Medien-Änderungen (Upload, Bearbeitung, Löschung) und Relations-Änderungen (Anlegen, Bearbeiten, Löschen) auf beiden verknüpften Datensätzen, inkl. lesbarem Label des jeweils anderen Datensatzes.
- Backend: neue Relationsvokabulare erhalten automatisch einen unrestriktiven Standardterm ("ist verknüpft mit"), damit freie Relationen auch ohne vorherige Admin-Konfiguration einen nutzbaren Typ haben.
- Backend: `diff_fields()` zeigt geänderte Metadatenfelder jetzt einzeln mit tatsächlichem Alt-/Neu-Wert (`metadata.<feld>`) statt der gesamten Metadaten als einen pauschalen "geändert"-Eintrag.

## [1.0.1] - 2026-08-18

### Fixed
- Admin: Banner mit Ablaufdatum ließen sich nicht speichern – `expires_at` kam vom Frontend als timezone-aware Timestamp, die DB-Spalte ist aber naiv; asyncpg lehnte den Insert/Update ab. `expires_at` wird jetzt vor dem Speichern auf naiv normalisiert.
- Admin: Audit-Log zeigte bei jeder Objekt-/Entity-/Place-/Occurrence-Änderung sämtliche Felder als "geändert" an, auch unveränderte (z. B. `status: draft → draft`), und Metadaten-Diffs erschienen als `[object Object]`. Neue `diff_fields()`-Hilfsfunktion loggt nur tatsächlich geänderte Felder und zeigt Objekt-/Array-Werte (Metadaten) als "geändert" statt als rohes JS-Objekt.
- Backend: `idno` fehlte beim Objekt-Update im "neu"-Teil des Audit-Diffs (`places`/`occurrences` hatten zusätzlich `metadata` gar nicht im Diff und nutzten ungetrimmtes `idno`) – für alle vier Bestandstypen konsistent gemacht.

## [1.0.0] - 2026-08-17

### Added
- Medienformate über Bilder hinaus: PDF, Audio (MP3/WAV/OGG), Video (MP4/WebM) und 3D-Modelle (GLB/GLTF) sind jetzt als Medien-Dateien hochladbar. Nicht-Bild-Dateien überspringen die Cantaloupe/IIIF-Pipeline und sind sofort `ready`; Bilder bleiben unverändert auf dem IIIF-Pfad.
- Portal: neuer Viewer-Dispatch nach MIME-Kategorie – PDF im nativen Browser-Viewer, Audio/Video als HTML5-Player, 3D-Modelle über `@google/model-viewer` (lazy geladen, eigener Chunk).
- Backend: `_links.thumbnail` und IIIF-Manifest werden nur noch für Bild-Dateien erzeugt; MIME-Fallback für `.glb`/`.gltf` (Browser senden oft leeren Content-Type).
- Portal: Thumbnail-Streifen unter dem primären Medium (gleichgroße Thumbnails, Klick wechselt das große Display); sekundäre Nicht-Bild-Medien werden als Player mit Dateiname angezeigt.
- Admin: Medien-Lightbox (Klick aufs Medium öffnet Overlay-Viewer statt neuem Tab; auth-geschützte Datei wird als Blob geladen und als Object-URL abgespielt) plus Kategorie-Thumbnails (Video-Frame-Vorschau, kompaktes Audio, PDF-/3D-Icon).
- Backend: `category` jetzt auch im öffentlichen Portal-Endpoint `PortalMediaRead` (zuvor droppte Pydantic das Feld, wodurch das Portal Audio/Video nicht als Nicht-Bild erkannte).
- Mehrsprachigkeit: konfigurierbare Sprachliste (Admin → Einstellungen → Sprachen), mehrsprachige Labels (Schema, Subtypen, Formularvarianten, Vokabulare) und übersetzbare Text-/Rich-Text-Felder (`is_translatable`).
- Admin: Sprach-Editor pro konfigurierter Sprache; übersetzbare Felder zeigen die Primärsprache plus „+ XY"-Button zum Hinzufügen weiterer Sprachen.
- Portal: Sprachumschalter und dependency-freies i18n; übersetzbare Feldwerte und Labels werden in der aktiven Sprache angezeigt (Fallback Primärsprache → Deutsch → erste belegte Sprache).
- Migration `0036`: `field_definitions.is_translatable` und `admin_config.supported_languages`.

## [0.11.12] - 2026-08-17

### Fixed
- Admin: Medien-Thumbnails im Objektformular blieben leer (401), weil `<img>` gegen den authentifizierten `/v1/objects/{id}/media/{id}/file`-Endpoint lud – Bearer-Token liegt in `localStorage`, `<img>` sendet keinen `Authorization`-Header. Backend liefert jetzt `_links.thumbnail` (öffentliche, unauthentifizierte Cantaloupe-IIIF-URL) im Media-Serializer, Admin-Frontend nutzt diese für die Vorschau.
- Admin: Statischen "Stage"-Badge aus dem Sidebar-Header entfernt.
- Portal (mobil): Header-Suchfeld nutzte fälschlich die `hero-search`-Klasse (`margin: 0 auto`), wodurch es als Flex-Item zentriert statt gestreckt wurde – eigenes Styling statt Klassen-Wiederverwendung. Wrapper-Div des Header-Suchfelds hatte zudem keine Breite gesetzt, wodurch `width: 100%` auf das innere Formular wirkungslos blieb.
- Portal (mobil): Mobile Breakpoint-Overrides für `.container`/`.site-header` nutzten die `padding`-Shorthand und überschrieben damit das vertikale Padding aus dem vorherigen Breakpoint vollständig (vor allem bei ≤480px) – auf `padding-left`/`padding-right` umgestellt, damit sich Breakpoints nicht gegenseitig stompen.
- Portal (mobil): Header-Suchfeld doppelte sich mit dem Hero-Suchfeld auf der Startseite – Header-Suche wird auf `/` mobil ausgeblendet, bleibt auf allen anderen Seiten sichtbar.
- Portal (mobil): "Suche verfeinern"-Formular auf der Suchergebnisseite hatte zu wenig Abstand zum Header und Eingabefeld/Button nebeneinander statt korrekt proportioniert.

## [0.11.11] - 2026-08-17

### Fixed
- Portal: Mobile-Overflow behoben (#303) – globaler `overflow-x: hidden`-Schutz gegen Grid-Intrinsic-Sizing-Overflow, `min-width: 0` auf `.detail-layout`/`.search-layout`-Grid-Kindern, IIIF-Viewer-Wrapper mit `width: 100%` begrenzt, `RelationsList`-Zeilen brechen jetzt um, Card-/Result-Titel mit `overflow-wrap: anywhere` gegen lange unbrochene Strings abgesichert.

## [0.11.10] - 2026-08-17

### Added
- Admin: Rollenrechte-Matrix aus `#users` in eigene Unterseite `#user-roles` ausgelagert.

### Fixed
- Admin: `#schema`, `#vocab`, `#pages`, `#users` waren im Sidebar für nicht-Admin-Rollen ausgeblendet, aber via direkter Hash-Navigation erreichbar (AppShell fehlte `isAdmin`-Gate). Backend-Endpunkte waren bereits korrekt serverseitig auf admin/superuser beschränkt.

## [0.11.9] - 2026-08-17

### Fixed
- nginx: `location /api/` schnitt den `/api/`-Präfix vor dem Proxying ab (`rewrite ^/api/(.*)$ /$1 break;`), obwohl die App `docs_url`/`redoc_url`/`openapi_url` mit vollem `/api/...`-Pfad registriert. `/api/docs`, `/api/redoc` und `/api/openapi.json` lieferten dadurch 404 über den äußeren nginx (Compose-Basisstack, `docker/nginx.conf`). Rewrite entfernt, Verhalten jetzt analog zu `location /v1/`.

## [0.11.8] - 2026-08-17

### Added
- Importer: Auto-Mapping-Heuristik für CSV/Excel-Spalten (exakter Treffer → Synonym-Tabelle → Levenshtein-Fuzzy-Match, Issue #199).

## [0.11.7] - 2026-08-17

### Changed
- Almanac/Wissensbasis-Sync: Decisions-Index, Audit/Snapshot-Workflow, Admin-Routes-Referenz, Roadmap-Seite aktualisiert; `.agents/IMPLEMENTIERUNGSPLAN.md` entfernt (ersetzt durch GitHub-Roadmap).

## [0.11.6] - 2026-08-16

### Added
- Tests: Multi-Page-Roundtrip für OAI-PMH ResumptionToken; Snapshot-Restore-Inhaltsprüfung für alle Primärtypen (Issue #301).

## [0.11.5] - 2026-08-14

### Added
- Anonymer Portal-Read-Model unter `/portal/v1` (nur veröffentlichte Objects, Entities, Places, Occurrences; keine Vorgänge).
- `_links`-Navigation in den JSON-Antworten der privaten `/v1`- und öffentlichen `/portal/v1`-API (Records, Medien, Vokabulare, Terms).
- Einzel-Endpunkte für Vokabular und Term in `/v1` und `/portal/v1`.

### Changed
- Die Arbeits-API unter `/v1` verlangt jetzt ein Token (JWT oder API-Key); zuvor waren Lesezugriffe anonym möglich.
- Portal-Client nutzt `/portal/v1` statt `/v1`.

### Removed
- Anonymer Feedback-Schreibendpunkt; `/v1/feedback` bleibt tokenpflichtig erhalten.

### Security
- Portal-Antworten nutzen explizite öffentliche Projektionen: interne Felder (Version, Search-Vector), Relations-Metadaten, unfertige Medien und Vorgänge bleiben verborgen.
- `/portal/v1` ist in allen Nginx-Konfigurationen vor dem SPA-Fallback zum Backend geroutet.

## [0.11.4] - 2026-08-14

### Changed
- CodeAlmanac für KI-Feldvorschläge, OAI-/Vocabulary-LOD-Grenzen und die Distribution per katalon-cli aktualisiert.

## [0.11.3] - 2026-08-14

### Changed
- KI-Feldvorschläge zeigen bei vorhandenen Werten einen editierbaren Vergleichsdialog; Vision-Bilder werden auf maximal 1024 px begrenzt und das Input-Token-Limit vor dem Provider-Aufruf geprüft. (#114)

## [0.11.2] - 2026-08-14

### Added
- Kontextsensitives Hilfe-Icon in der Admin-Topbar, das je nach Screen auf die passende Anwenderdoku-Seite verlinkt (`ROUTE_DOCS`-Mapping).

### Changed
- Anwenderdoku (`docs/`) an aktuellen Stand nachgezogen: neue Seiten für Formularvarianten und Subtypen, Architektur-Doku um Deep-Linking, Onboarding-Tour, granulare Rollenrechte und aktuelle Admin-Screen-Liste ergänzt, Produktionsdoku um katalon-cli als empfohlenen Installationsweg ergänzt.

## [0.11.1] - 2026-08-13

### Added
- Admin-Screens mit internen Tabs/Filtern (Einstellungen, Audit-Log, statische Seiten, Subtypen, Importer, Schema-Editor, Formularvarianten, Datensatzlisten) sind per URL-Hash direkt verlinkbar, z. B. `#settings/medien` oder `#schema/object.foto`.

## [0.11.0] - 2026-08-13

### Added
- Vorgangstypen sind als Subtypen konfigurierbar und können eine Beschreibung ihres institutionellen Einsatzes enthalten. Die Beschreibung erscheint beim Anlegen und Bearbeiten eines Vorgangs. (#255)
- Admin-Einstellungen zeigen die Versionshinweise der laufenden Katalon-Version.

### Changed
- Die sechs bisherigen Vorgangstypen sind ein löschbarer Startbestand. Solange kein Vorgang einen Typ verwendet, lassen sich Typ, zugehörige Schemafelder und Formularvarianten samt Rollen-Defaults kontrolliert entfernen.

### Fixed
- Admin zeigt textuelle 409-Fehlermeldungen der API anstatt einer irreführenden generischen Relationsmeldung.
- Die Onboarding-Tour verweist für Normdaten auf den Schema-Editor.

## [0.10.30] - 2026-08-13

### Added
- Einstellungen bieten einen bestätigungspflichtigen Schema-Reset je Datensatztyp oder Subtyp; Metadaten bleiben erhalten und werden bei erneut angelegtem Feld gleichen technischen Namens wieder sichtbar.

### Fixed
- Die Aktion für freie Beziehungen bleibt in der schmalen Formularseitenleiste vollständig lesbar.

## [0.10.29] - 2026-08-13

### Added
- Vorgänge verwenden konfigurierbare Subtypen. Die sechs bisherigen Vorgangstypen bleiben als geschützte Systemtypen erhalten; eigene Typen können Felder, Formularvarianten und Listenfilter nutzen. (#255)

### Changed
- Vorgänge haben keine Snapshots mehr; Beziehungen bleiben über den generischen Relationsgraphen verfügbar.

## [0.10.28] - 2026-08-13

### Added
- Konfigurierbare CRUD-Rechte für feste Rollen je Primärtyp, mit serverseitiger Durchsetzung und Rollenmatrix in der Benutzerverwaltung. (#276)

## [0.10.27] - 2026-08-13

### Fixed
- Relationsfelder zeigen den Relationstyp als Dropdown rechts neben der Suche; Datensätze lassen sich bereits vor der Typauswahl suchen.

## [0.10.26] - 2026-08-13

### Fixed
- Datumsfelder normalisieren europäische Eingaben, bieten einen Kalender und weisen ungültige Kalenderdaten ab.

## [0.10.25] - 2026-08-13

### Changed
- Primärtypen starten ohne impliziten Subtyp; bestehende Basiswerte werden zu allgemeinen Datensätzen migriert.
- Listen bieten bei konfigurierten Subtypen einen Typfilter.

## [0.10.24] - 2026-08-13

### Changed
- Relationsfelder benötigen ein Relationstyp-Vokabular.

## [0.10.23] - 2026-08-13

### Changed
- Lokales Upload-Verzeichnis `media/` wird nicht mehr versioniert.

## [0.10.22] - 2026-08-13

### Added
- Relationsfelder bieten bei erfolgloser Suche die passende Schnellanlage direkt im Treffer-Dropdown an.

### Fixed
- Verschachtelte Schnellanlage-Dialoge bleiben zugänglich und mobil bedienbar.

## [0.10.21] - 2026-08-13

### Changed
- Gefüllte Relationsfelder erscheinen als Chip mit sichtbarer Entfernen-Aktion.

## [0.10.20] - 2026-08-13

### Fixed
- Manuelle Snapshots werden mit der aktuellen Datensatzversion wiederhergestellt.

## [0.10.19] - 2026-08-13

### Fixed
- Medienkarte bleibt im rechten Formularbereich; Medienkacheln nutzen dessen volle Breite.

## [0.10.18] - 2026-08-13

### Changed
- Medien nutzen die volle Formularbreite; Beziehungen stehen vor verknüpften Vorgängen.

## [0.10.17] - 2026-08-13

### Changed
- Medienrechte werden pro Datei nach dem Upload bearbeitet; Instanz-Defaults werden beim Einzel- und Batch-Upload kopiert.

## [0.10.16] - 2026-08-13

### Fixed
- Relationsvokabulare sind flach; Elternrelationen werden auch beim Import abgewiesen.
- Relationstyp-IDs bleiben in der Vokabularansicht lesbar.

## [0.10.15] - 2026-08-13

### Fixed
- Feldgebundene Beziehungen scrollen zum Formularfeld und heben es kurz hervor.

## [0.10.14] - 2026-08-13

### Fixed
- Relationsfelder akzeptieren ein Relationstyp-Vokabular nur noch, wenn es für den konfigurierten Quell- und Zieltyp mindestens einen zulässigen Term enthält.

## [0.10.13] - 2026-08-13

### Added
- Relationsfelder können einen optionalen festen Relationstyp aus ihrem Vokabular festlegen. Feldgebundene und freie Beziehungen sind in der Admin-Karte getrennt; eingebettete Suchfelder berücksichtigen den festen Typ optional. (#213)

### Fixed
- Verknüpfte Portal-Facetten bleiben gespeichert; Änderungen der Einbettungs-Konfiguration reindizieren den Quelltyp automatisch.

## [0.10.12] - 2026-08-12

### Added
- Verknüpfte, im Schema ausgewählte Felder können im Portal als Facetten verwendet werden; deren Werte werden beim Indexieren und Reindexieren als Keyword-Facetten übernommen. (#213)

## [0.10.11] - 2026-08-12

### Fixed
- Relationstyp-Constraint-Vorschau korrekt als JSX-Fragment gruppiert, damit die Admin-App wieder kompiliert. (#291)

## [0.10.10] - 2026-08-12

### Added
- Relationstyp-Editor zeigt live, für welche Quell-/Zieltypen ein Term gilt, einschließlich Erklärung für leere Auswahlen. (#291)

## [0.10.9] - 2026-08-12

### Fixed
- E2E: Cantaloupe-Mount wird im GitHub-Runner mit `sudo` für den Backend-Prozess beschreibbar gemacht. (#221)

## [0.10.8] - 2026-08-12

### Fixed
- E2E: Der CI-Runner erhält Schreibrechte auf das Cantaloupe-Medienverzeichnis; der Relations-Test legt seinen benötigten Relationstyp isoliert als Testdaten an. (#221)

## [0.10.7] - 2026-08-12

### Fixed
- KI-Einstellungen zeigen den bisherigen Tagesverbrauch des angemeldeten Benutzers und den globalen Monatsverbrauch direkt neben den Limits. (#254)

## [0.10.6] - 2026-08-12

### Fixed
- E2E: Gemeinsame Admin-Anmeldung markiert das Onboarding vor Folgetests als abgeschlossen, damit der Tour-Overlay Interaktionen nicht blockiert. (#221)

## [0.10.5] - 2026-08-12

### Fixed
- Admin: `package-lock.json` mit den deklarierten Abhängigkeiten synchronisiert, damit der E2E-Workflow `npm ci` ausführen kann. (#221)

## [0.10.4] - 2026-08-11

### Added
- Vokabular-Import-UI: Hilfetext erklärt hierarchischen Import (`parent_term` akzeptiert ID oder Label des Elternterms) und die Slug-Ableitung aus dem Label. (#256)

### Fixed
- Admin: Vokabular-Import-Dialog blockierte CSVs ohne gemappte ID-Spalte — jetzt reicht auch eine Label-Spalte (ID wird slugifiziert, siehe #259).
- Backend: `CORS_ORIGINS` aus der Umgebung scheiterte am JSON-Parsing von pydantic-settings, sobald docker-compose/dotenv Quotes im Wert strippen — Container startete nicht mehr. `cors_origins` nutzt jetzt `NoDecode` + toleranten Validator (JSON-Array, Quote-lose Variante oder kommagetrennt).

## [0.10.3] - 2026-08-11

### Added
- Vokabular-Import: `term` ist jetzt optional — fehlt die Term-ID, wird sie aus dem Label slugifiziert (Umlaute `ä→ae` etc.). `parent_term` akzeptiert auch das Label des Elternterms und löst es auf den generierten Slug auf. (#259)

### Fixed
- Admin: `relType`-State im Relation-Input wird bei Wechsel der Typkombination (`relTypeVocabId`/`fromType`/`targetType`) zurückgesetzt statt sich auf den Remount-Key der Aufrufstelle zu verlassen. (#292)

## [0.10.2] - 2026-08-11

### Changed
- Almanac-Testing-Seiten aktualisiert (SHA-gepinnte GitHub Actions, Dependabot, Cantaloupe im E2E-Workflow) — dokumentiert bereits gemergten Stand aus 3d5dca7.

## [0.10.1] - 2026-08-11

### Fixed
- Fehlendes `data-tour`-Attribut am "Neu anlegen"-Button ergänzt, das für einen Onboarding-Tour-Schritt benötigt wird.

## [0.10.0] - 2026-08-11

### Added
- Relationstyp-Vokabulareinträge können auf Quell-/Ziel-Record-Typen eingeschränkt werden (`applies_from`/`applies_to`); Vokabular-Endpunkt filtert danach, Relation-API validiert serverseitig (422 bei unzulässiger Kombination).

## [0.9.0] - 2026-08-11

### Added
- Geführte Onboarding-Tour für Admin-Erstanmeldung (Rolle `admin`/`superuser`), jederzeit über Hilfe-Icon startbar, Fortschritt über `users.onboarding_completed_at` gespeichert.

## [0.8.1] - 2026-08-11

### Added
- Felder im Schema-Editor per Drag & Drop umsortieren.

## [0.8.0] - 2026-08-10

### Added
- Verknüpfte Objects, Entities, Places, Occurrences und Procedures lassen sich direkt aus Relationsfeldern und dem allgemeinen Beziehungen-Panel als Entwurf anlegen und automatisch verknüpfen (#277).
- Schema-gesteuerte Schnellanlage mit Formularvarianten, konfigurierbaren beziehungsweise festen Subtypen, responsivem Dialog und Fokus-Rückgabe.
- Playwright-Abdeckung für Draft-Anlage, gleichartige Object-Relation, Tastaturfokus und mobile Bedienung.

### Changed
- Cataloger können die für neue Datensätze benötigten Subtypen und ID-Nr.-Vorschläge lesen; schreibende Endpunkte bleiben durch `manage_content` geschützt.
- Backend-Integrationstests isolieren Rate-Limit-Zähler und Elasticsearch-Startup, sodass die Suite ohne externes Elasticsearch reproduzierbar läuft.

### Fixed
- Playwright wartet auf den tatsächlichen OpenAPI-Endpunkt `/api/openapi.json`.

## [0.7.8] - 2026-08-06

### Fixed
- Importer-Upsert (`merge`/`replace`) kapselt jeden Zeilen-Write jetzt in einem SAVEPOINT. Ein `StaleDataError` durch konkurrierende Änderung derselben Zeile rollt nur diese Zeile zurück (Zeile wird als Version-Konflikt übersprungen) statt die gesamte Session für den Rest des Import-Batches unbrauchbar zu machen.
- Datenbankseitiges Optimistic Locking (`version_id_col`) für Object, Entity, Place, Occurrence, Procedure statt rein Python-seitigem Check — schließt TOCTOU-Lücke bei konkurrierenden Speichervorgängen.
- Snapshot-Restore verlangt jetzt `If-Match` (`428`/`409`), erhöht die Version, schreibt Audit `restore` und synchronisiert Schema-Relationen, statt konkurrierende Änderungen lautlos zu überschreiben.
- Delete-Endpunkte (Object/Entity/Place/Occurrence/Procedure) flushen den Löschvorgang vor Elasticsearch-Entfernung und Cleanup-Task-Dispatch — verhindert verwaiste ES-Dokumente und Relations-Cleanup bei fehlgeschlagenem Delete durch Versionskonflikt.
- Aktive Ausleihvorgänge (`loan_out`) sperren jetzt die betroffenen Objektzeilen bei Relationserstellung, Aktivierung und Snapshot-Restore — verhindert doppelte aktive Ausleihen unter Nebenläufigkeit.
- Place-Update setzt Geometrie vor dem Flush statt danach — verhindert doppelte Versionierung durch zwei getrennte UPDATEs pro Request.
- PID-Registrierung und Publish-Flow nutzen jetzt denselben versionierten Flush wie reguläre Updates.
- Cleanup-Task nach Delete erkennt `StaleDataError` und retried statt fehlzuschlagen.

## [0.7.6] - 2026-08-05

### Added
- Admin bei 319/375/768 px vollständig bedienbar (#253): responsive Header, Toolbars, Tabs, Tabellen, Pagination, Formulare über alle Admin-Screens.
- Playwright-Spec `admin-responsive.spec.ts` für Liste (319 px), Schema (375 px) und Formular (768 px).
- Cantaloupe-Service im CI-E2E-Workflow, sonst startet Backend dort nicht.

### Fixed
- Listen-Pagination oberhalb von Seite 10 war unerreichbar.
- Formular: Status ließ sich nach Erstanlage ändern, ohne dass gespeichert werden konnte; Portal-Link folgte ungespeichertem statt gespeichertem Status.
- Diverse mobile Touchziele unter 44 px, fehlende Tabellen-Scrollcontainer, Hover-only-Aktionen.

### Changed
- E2E-Runner startet Dev-Compose-API im Vordergrund statt per Hintergrund-`up -d` (vermeidet Start-Race).

## [0.7.5] - 2026-08-05

### Added
- KI-Unterstützung für geeignete Subfelder wiederholbarer Containergruppen (#279): Konfiguration im Schema-Editor und Vorschläge pro konkreter Gruppeninstanz.

### Changed
- Gruppen-KI übergibt ausschließlich die aktuell sichtbare Instanz als Gruppenkontext, bestätigt das Ersetzen vorhandener Werte und übernimmt Vorschläge nur in den lokalen Formularzustand.

## [0.7.4] - 2026-08-05

### Added
- Authority-Felder als Subfelder wiederholbarer Containergruppen (#278), inklusive Quellenwahl, Autocomplete und strukturierter Validierung.

### Changed
- Gemeinsames Authority-Autocomplete unterstützt Tastatursteuerung und ARIA-Combobox-Semantik; deaktivierte Quellen und folgenreiche Quellenwechsel werden im Schema-Editor sichtbar behandelt.
- Projektworkflow prüft vor Umsetzungen UX-Einwände und relevante CodeAlmanac-Seiten und aktualisiert den Almanac anschließend.

## [0.7.3] - 2026-08-04

### Fixed
- Admin-Linting mit einer minimalen ESLint-Flat-Config wiederhergestellt und bestehende Lintfehler bereinigt.

## [0.7.2] - 2026-08-04

### Fixed
- Formularvarianten können optionale Gruppen mit aktiven Pflicht-Unterfeldern nicht mehr ausblenden (#282). Die Admin-Oberfläche wählt solche Gruppen automatisch aus, sperrt sie gegen Abwahl und beschränkt globale Varianten korrekt auf globale Felder.

## [0.7.1] - 2026-08-03

### Fixed
- Formularvarianten (#275) konnten Pflichtfelder auf oberster Schemaebene ausblenden: `validate_metadata` prüft required-Status immer gegen das volle Schema, unabhängig von der Variante. Backend (`form_variants.py`) lehnt solche Varianten jetzt ab; `ScreenFormVariants` zeigt die Pflichtfelder gesperrt an und selektiert sie bei neuen Varianten automatisch vor.

## [0.7.0] - 2026-08-03

### Added
- Formularvarianten je Datensatztyp und Subtyp (#275): Admins können in Konfiguration → Formularvarianten benannte Varianten anlegen, die eine Teilmenge vorhandener Felddefinitionen auswählen und ordnen (Voll-, Schnellerfassung, workflow-spezifische Masken). Gespeicherte Metadaten bleiben unabhängig von der gewählten Variante. Neue Tabellen `form_variants` und `form_variant_role_defaults` (Migration 0028), Endpunkte unter `/v1/form-variants`.
- Formular-Tab-Leiste in Objekt-/Entity-/Place-/Occurrence-/Vorgangsformularen: Variante wird nach Priorität aufgelöst (Kontext-Override > gemerkte manuelle Wahl > Rollen-Default > globaler Default > Vollschema als Fallback), letzte manuelle Wahl bleibt pro Typ/Subtyp lokal gespeichert.

## [0.6.4] - 2026-07-15

### Fixed
- CI: `test_reindex_type_accepts_procedure` schlug seit v0.6.2 fehl. `enqueue_or_503()` (#274) ruft immer `task.delay(...).id` auf; der Test-Mock `fake_delay` gab `None` zurück statt eines Objekts mit `.id` (wie echtes Celery `AsyncResult`). Mock korrigiert, kein Produktionscode geändert.

## [0.6.3] - 2026-07-15

### Changed
- OpenAPI-Dokumentation finalisiert (Phase 12 Hardening): `/api/openapi.json`-`info.version` liest jetzt live aus dem installierten Paket (`importlib.metadata`) statt fest verdrahtetem `"0.1.0"`. Alle 30 Router-Tags haben jetzt eine Kurzbeschreibung (`openapi_tags` in `main.py`). Alle 149 Endpunkte über 30 Dateien in `api/v1/` haben `summary=` und, wo zutreffend, `responses={...}` für tatsächlich geworfene 400/403/404/409/422/503-Fälle (Rollen-Check, `If-Match`-Konflikt, Relation-Konflikt beim Löschen, Broker-Ausfall bei `enqueue_or_503`).

## [0.6.2] - 2026-07-13

### Fixed
- Broker-Ausfall bricht keine schreibenden Requests mehr (#274). Fire-and-forget-`.delay()`-Aufrufe im Request-Pfad (Relation-Cleanup bei Delete aller 5 Typen, IIIF-Tile-Generierung beim Upload, Schema-Reindex) liefen bei nicht erreichbarem Redis in ein 500, obwohl der DB-Schreibvorgang bereits erfolgreich war. Neuer Helper `workers/enqueue.py`: `enqueue()` loggt Broker-Fehler und macht weiter, `enqueue_or_503()` liefert für job-id-basierte Endpunkte (Batch-Media-Import, Record-Import) sowie explizit nutzer-getriggerte Reindex-/Reconciliation-Endpunkte ein sauberes 503 statt 500. Entfernt nebenbei ein stilles `except: pass` in `schema_admin.py`.

### Fixed
- Integration-Tests: `test_object_crud_roundtrip` (und alle schreibenden Pfade) liefen ins Leere, weil `.delay()` einen Redis-Broker erwartet, den die Testumgebung (nur Postgres via testcontainers) nicht hat. Neue autouse-Fixture stellt Celery im Test auf einen In-Memory-Broker um — `.delay()` enqueued ohne Redis, Task-Body läuft nicht (kein Worker). Kein Produktionsverhalten geändert.

### Added
- Optimistic Locking gegen stilles Überschreiben bei parallelem Edit (#272): alle 5 Record-Typen haben eine `version`-Spalte (Migration 0027). PUT erwartet `If-Match: <version>`; bei veralteter Version antwortet das Backend mit `409 {"error":"version_conflict","current_version":N}` statt blind zu überschreiben. Fehlt der Header (Importer/Skripte), bleibt das alte Verhalten.
- Admin-UI: Bearbeitungskonflikt-Dialog mit feldweisem 3-Wege-Merge. Bei 409 holt die UI den Serverstand und vergleicht pro Metadatenfeld `base`/`server`/`mine`; nur echte beidseitige Kollisionen werden abgefragt, der Rest automatisch gemergt. B's ungespeicherte Änderungen bleiben dabei erhalten. Skalare (idno/status/…) werden aus B's Payload übernommen.

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
