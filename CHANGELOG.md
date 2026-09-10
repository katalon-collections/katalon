# Changelog

All notable changes to Katalon are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), versioning: [Semantic Versioning](https://semver.org/).

## [1.29.0] - 2026-09-10

### Added
- Portal-Terminologie pro Installation konfigurierbar (Issue #373):
  `PortalConfig.terminology` erlaubt es, die Bezeichnung der Kerntypen
  (Objekte, Entitäten, Orte, Occurrences, Sammlungen) im Portal zu
  überschreiben, getrennt nach Singular/Plural und pro Sprache — z. B.
  „Werk"/„Werke" statt „Objekt"/„Objekte" für eine bibliothekarische
  Installation. Reine Präsentationsschicht: interne Record-Type-Keys,
  API-Routen/Payloads und Berechtigungen bleiben unverändert. Im Portal
  läuft die Auflösung zentral über `typeLabel()`/`t()` in `i18n/index.ts`,
  sodass Hauptnavigation, Startseite, Suchergebnisse, Facetten und
  Detailseiten die konfigurierten Begriffe automatisch übernehmen, ohne
  dass jede Stelle einzeln angepasst werden musste. Fehlt eine Übersetzung
  oder ein Override, greift die eingebaute Standardterminologie — im Admin
  unter Einstellungen → Terminologie mit „Auf Standard zurücksetzen" pro Typ.

## [1.28.0] - 2026-09-10

### Added
- Portal-Startseite konfigurierbar über Inhaltsbausteine (Issue #374):
  `PortalConfig.homepage_blocks` (geordnetes JSONB-Array) ersetzt die feste
  Reihenfolge „Highlights → Neueste Objekte". Blocktypen: `text` (mehrsprachig,
  frei formulierbar), `objects` (neueste Objekte, Anzahl konfigurierbar),
  `curated` (nutzt die bestehenden `featured_object_ids` unter Portal &
  Institution, keine Doppelpflege) und `collections` (oberste Sammlungen,
  alle Sammlungen oder eine manuell gewählte Auswahl). Blöcke lassen sich im
  Admin unter Einstellungen → Startseite hinzufügen, umsortieren
  (Hoch/Runter), aktivieren/deaktivieren und entfernen. Bestehende
  Installationen erhalten per Migration automatisch die bisherige
  Blockkonfiguration (`curated` + `objects`), damit die Startseite nach dem
  Upgrade nicht leer bleibt. Fehlende/gelöschte referenzierte Sammlungen oder
  Objekte werden beim Rendern übersprungen statt die Seite abstürzen zu
  lassen. Arbeitslisten wurden bewusst nicht als Quelle angebunden — das
  Konzept ist für persönliche/geteilte Merklisten gedacht, nicht für
  öffentliche Kuration; `curated` deckt den Anwendungsfall stattdessen über
  das bereits vorhandene Feld ab.

## [1.27.0] - 2026-09-10

### Added
- S3-kompatibles Objektspeicher-Backend für Medien (strikt opt-in, Issue #121):
  `STORAGE_BACKEND=s3` neben dem unveränderten Default `local`. Zielklasse sind
  alle S3-kompatiblen Implementierungen — Ceph RADOSGW, MinIO, Hetzner Object
  Storage, Garage, AWS S3. Der Backend-Client (boto3, in `asyncio.to_thread`)
  weicht bewusst von boto3-Defaults ab: `request_checksum_calculation=
  "when_required"` (botocore ≥ 1.36 sonst `x-amz-checksum-crc32` → 400 bei
  vielen kompatiblen Implementierungen), Path-Style als Default, explizite
  Region, konfigurierbare TLS-Verifikation (`S3_VERIFY_TLS`, `S3_CA_BUNDLE`
  für On-Prem-Ceph mit interner CA). Cantaloupe liest via nativem `S3Source`
  direkt aus dem Bucket — weil Cantaloupe 5.0.x kein Path-Style kennt
  (virtual-hosted addressing), muss `<bucket>.<endpoint-host>` DNS-seitig
  auflösbar sein. Private Medien werden durchs Backend gestreamt, keine
  Presigned-URLs (kein Auth-Bypass). Neue Compose-Overrides:
  `docker-compose.s3.yml` (Produktion) und `docker-compose.minio.yml`
  (Dev-only MinIO zum Testen ohne Cloud-Account). Logos/Themes und
  Batch-Import-Staging bleiben lokal. Kein Migrationsskript: bestehende
  local-Instanzen sind unverändert, nur neue Instanzen starten mit S3.

## [1.26.13] - 2026-09-10

### Fixed
- Admin → Einstellungen → Facetten: Toggling eines Feldes vom Typ `authority`
  (Normdaten-Feld) als Facette schlug fehl, sobald die im Feld hinterlegte
  `settings.source` unbekannt oder deaktiviert war — auch wenn nur `is_facet`
  geändert wurde. Die Validierung in `schema_admin._validate_field_settings`
  greift jetzt nur noch, wenn sich `source` tatsächlich ändert (analog zum
  bestehenden PID-Provider-Grandfathering). Da das PUT bei Fehlschlag
  komplett verworfen wurde, ohne den lokalen Checkbox-Zustand zurückzusetzen,
  wirkten Facetten- und „Ergebnis-Untertitel"-Auswahl im UI gespeichert,
  obwohl der Server nichts übernommen hatte — sichtbar erst nach einem
  manuellen Reload.

### Added
- Admin → Einstellungen → Facetten → „Ergebnis-Untertitel": Die ID-Nummer
  (`idno`) steht jetzt immer als Option zur Verfügung, unabhängig davon, ob
  sie als Facette aktiviert ist — analog zu Typ/Status. Der öffentliche
  Portal-Search-Endpunkt löst `idno` direkt aus dem Datensatz auf, da es kein
  Feld mit `facet_all_*`-Aggregation ist.

## [1.25.0] - 2026-09-09

### Added
- Rollenkonzept (#371, Phase 2): Vollständige Überarbeitung des Berechtigungssystems.
  - Viewer: Standard-Leseberechtigung auf 6 Typen (ohne Vorgänge und Lagerorte),
    per Matrix abschaltbar
  - Cataloger: CRU (kein Löschen), darf Lagerorte nur lesen
  - Editor: CRUD + Status-Wechsel + Vokabular-Struktur + Lagerorte verwalten
  - Admin: Force Unlock, erweiterte Konfiguration
- `feature_permissions`-Tabelle: feingranulare Feature-Rechte (Export, SPARQL,
  Import, Vokabular, etc.), konfigurierbar über die Admin-UI, Defaults pro Rolle
  aus dem Rollenkonzept, Feature-Liste im JWT-Token
- `RolePermission` um `collection`, `storage_location`, `vocabulary_term` erweitert
- Backend Feature-Gates: Export, SPARQL, Import, Audit, Working-Sets, Vokabular,
  Statische Seiten, OAI-Sets, Banner, Lagerorte über `require_feature()` statt
  hartem `require_role("admin")` — Admin kann über UI konfigurieren
- Frontend Sidebar/AppShell: Feature-basierte Anzeige statt `isAdmin`-binär-Gate
- Manual Exclusive Lock (#371, Phase 2): Persistente exklusive Sperre mit
  Besitzer, Grund, Ablaufdatum (max. 7 Tage). Owner-Release, Editor darf
  Cataloger-Locks aufheben, Admin+ Force Unlock. Audit-Log. Banner im Formular.
- Automatischer Lock-Ablauf nach 7 Tagen; Erinnerungshinweis in der UI

## [1.23.0] - 2026-09-09

### Added
- Admin-UI / Audit-Log: Serverseitige Suche nach Datensatz, Kennung, Bearbeiter, Aktion oder Änderungsinhalt, mit Datumsfilter und Pagination. Die Ansicht ist damit auch für große, migrierte Bestände vollständig durchsuchbar.
- Admin-UI / Datensatzlisten: Ein Klick auf den primären Labelwert öffnet einen Datensatz direkt zur Bearbeitung; das Aktionsmenü bleibt weiterhin verfügbar.

### Fixed
- LIDO-Export: Entfernt bildpostkartenspezifische Vorgaben für Institution, Sammlung, Objekttyp, Ereignisse, Rechte und Medien. LIDO übernimmt fachliche Werte jetzt ausschließlich aus aktivierten Mapping-Regeln; die schemaerforderlichen Zielfelder Titel und Objekttyp werden vor der Veröffentlichung geprüft.

## [1.22.0] - 2026-09-08

### Added
- Admin-UI / Formulare: Konfigurierbare Formularabschnitte pro Datensatztyp und Subtyp. Admins ordnen Schemafelder benannten Abschnitten zu; das Erfassungsformular zeigt diese als Tabs, lässt nicht zugeordnete Felder unter „Allgemein“ und markiert Tabs mit Validierungsfehlern.

## [1.21.0] - 2026-09-08

### Added
- Portal / Detailseiten: Metadatenfelder, die im Schema als Facette (`is_facet`) markiert sind, werden auf den Objekt-, Personen-, Orts-, Werk- und Sammlungs-Detailseiten als klickbare Links dargestellt. Ein Klick führt zur Suche, gefiltert auf denselben Wert und Datensatztyp (`meta_<feld>=<wert>` bzw. bei Zahlenfeldern `range_<feld>_from/_to`). Betrifft `DetailPageLayout.tsx` (Objekt/Person/Ort/Werk) und den manuellen Feld-Loop in `CollectionDetailPage.tsx`; Backend liefert dafür `is_facet` neu über `GET /portal/v1/schema/{target_type}`.

### Fixed
- Admin-UI / Einstellungen: Das Speichern von Facetten unter „Einstellungen → Facetten“ synchronisiert direkte Schema-Facetten (`is_facet`) und geerbte Facetten nun zuverlässig mit dem Backend. `PUT /v1/portal/config` liefert die vollständig dynamisch aufgelöste Konfiguration zurück, und die UI serialisiert Schema- und Portal-Config-Updates, sodass aktive Facetten nach dem Speichern, Tab-Wechseln und Neuladen stabil erhalten bleiben.

## [1.20.1] - 2026-09-07

### Fixed
- SPARQL / Validation: Import von `ParseException` aus `pyparsing.exceptions` korrigiert (statt fälschlich aus `rdflib.plugins.sparql.parser`), wodurch SPARQL-Validierungs- und Unit-Tests fehlschlugen.

## [1.20.0] - 2026-09-07

### Added
- Admin-UI / Arbeitslisten (Working Sets): Neuer Menüpunkt „Arbeitslisten“ (`ScreenWorkingSets.tsx`) für ad-hoc, typgebundene Gruppierungen von Datensätzen für interne Workflows (Ausstellungsvorbereitungen, Prüflisten, Dublettenbereinigung, Kuration).
- Admin-UI / Listenintegration: Auswahlen in allen Datensatzlisten (`ScreenList.tsx`) können über die Massenaktionsleiste („Zu Arbeitsliste“) direkt in bestehende oder neu angelegte Arbeitslisten übernommen werden (`AddToWorkingSetModal.tsx`).
- Admin-UI / Detailansicht & Sortierung: Detailansicht von Arbeitslisten mit Reordering (Hoch/Runter), individuellen Notizen pro Datensatz, Thumbnails und direkter Verlinkung in die Bearbeitungsmaske.
- Admin-UI / Batch-Editing-Brücke: Nahtlose Übergabe aller Datensätze einer Arbeitsliste in das bestehende `BatchEditModal` zur gemeinsamen Status-, Feld- oder Relationsänderung.
- Backend / Arbeitslisten-Datenmodell: Neue PostgreSQL-Tabellen `working_sets` und `working_set_items` (Alembic-Migration `0057_working_sets.py`) mit Kaskadenlöschung und Berechtigungskontrolle (privat vs. geteilt).
- Backend / REST-API: Vollständige Endpunkte unter `/v1/working-sets` zur Erstellung, Verwaltung, Reordering und Befüllung von Arbeitslisten inklusive automatischer Titel- und Kennungsauflösung.

## [1.19.2] - 2026-09-03

### Fixed
- Backend: Relations-Label-Auflösung kannte den Datensatztyp `storage_location` nicht — verknüpfte Lagerorte zeigten im Objektformular "Nicht verfügbar" statt ihres Namens.
- Admin-UI: Lagerort-Suche im Beziehungs-Picker lief über die Volltextsuche, die Lagerorte gar nicht indiziert — die Suche fand nie Treffer. Fragt jetzt direkt die Lagerort-Liste ab, zeigt beim Fokussieren sofort bis zu 20 Einträge (kein Mindest-Zeichen mehr nötig) und filtert bei Eingabe weiter.
- Admin-UI: "Lagerort-Typ" hat jetzt ein Info-Popover (Zweck, wo neue Typen angelegt werden).

### Changed
- Lagerorte haben kein Entwurf/Intern/Öffentlich-Statusfeld mehr — sie waren nie im Portal oder in der öffentlichen Suche sichtbar, das Feld war wirkungslos. Die Inventarnummer/ID ist jetzt stattdessen immer Pflicht (außer bei konfigurierter automatischer Nummernvergabe), statt nur bei Nicht-Entwurf. Migration `0055` entfernt die `status`-Spalte und setzt `idno NOT NULL`.

## [1.16.0] - 2026-09-02

### Added
- Admin-Kopfsuche durchsucht neben Bestandsdaten auch Nutzer, Vokabulare und Terme, statische Seiten, OAI-Sets, Schemafelder, Subtypen, Formularvarianten, Banner und konfigurierte Normdatenquellen. Die Suche öffnet passende Admin-Bereiche direkt und verwendet für Konfigurationsdaten PostgreSQL statt eines zusätzlichen Suchindex.

### Changed
- Die Admin-Hilfe öffnet die veröffentlichte Anwenderdokumentation auf GitHub Pages statt Markdown-Dateien im Quellrepository.
- Subtypen: Beim Anlegen wird der interne Name automatisch aus dem Label abgeleitet (z. B. „Person" → `person`) und lässt sich bis zum Speichern anpassen. Nach dem Speichern bleibt er wie bisher unveränderlich.

### Fixed
- Portal-Abhängigkeiten und der IIIF-Viewer wurden auf sichere Versionen aktualisiert. Äußeres nginx liefert nun CSP-, HSTS- (Produktion), MIME-, Frame-, Referrer- und Permissions-Schutzheader aus.
- Portal-Kopfzeile: Suchfeld mit Autocomplete-Vorschlägen hatte `aria-expanded`/`aria-controls` ohne passende ARIA-Rolle gesetzt, was Screenreadern die Beziehung zur Vorschlagsliste unzugänglich machte (axe: `aria-allowed-attr`). Das Feld trägt jetzt `role="combobox"` und `aria-autocomplete="list"`.

