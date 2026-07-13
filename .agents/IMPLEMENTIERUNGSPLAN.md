# Katalon – Implementierungsplan

## Stand: 2026-07-06

GitHub Roadmap: https://github.com/users/karkraeg/projects/1

---

## Erledigte Phasen

### Phase 0 – Infra ✅
Docker Compose: api, worker, db (PostGIS), elasticsearch, redis, cantaloupe, admin, portal, nginx.
`docker/nginx.admin.conf` und `docker/nginx.portal.conf` für statische SPA-Container; `docker/nginx.conf` als Reverse Proxy.

### Phase 1 – Core-Datenbank ✅
ORM-Models für alle 4 Primärtypen, Relationen, Audit Log, Snapshots, Media, Vokabulare, Users.
Alembic-Migrationen laufen.

### Phase 2 – Schema-Engine ✅
`field_definitions`-Tabelle, `schema_service.validate_metadata()`, CRUD-Endpoints.
Vokabulare mit hierarchischen Terms vollständig.

### Phase 2.1 – Containerfelder (verschachtelte Metadatengruppen) ✅ – Issue #220
`field_type = "group"` mit `parent_id` (self-referential FK, CASCADE DELETE).
Sub-Felder inline im Schema-Editor verwaltbar; wiederholbare Gruppen im Formular mit nested Inputs.
ES-Indexierung als `nested`-Typ. Rekursive Validierung in `schema_service.validate_metadata()`.

### Phase 3 – CRUD alle 4 Typen ✅
REST-Endpoints für Objects, Entities, Places, Occurrences, Relationen.
Pagination, Status-Filter, Fulltext-Suche (PostgreSQL `search_vector`).

### Phase 4 – Auth + Audit Log ✅
JWT-Auth (jose), Rollen (admin/editor/viewer), bcrypt (direkt, ohne passlib).
Default-Admin-User wird beim ersten Start angelegt (`admin@katalon.dev / admin`).
Audit Log bei jedem Create/Update/Delete.

### Phase 5 – Media ✅ / IIIF ✅
Upload (Single-File), Celery-Task, Speicherung. IIIF-Manifest-Endpoint vorhanden.
`media_type`-Feld pro Datei; konfigurierbare Typen via Vokabular "media_types" (Vorderseite, Rückseite, Detail …).
Cantaloupe-Integration für Tile-Generierung ist verdrahtet: Celery-Task `generate_iiif_tiles` ruft Cantaloupes `info.json` auf und speichert das IIIF-Manifest in der DB.
Thumbnail-Vorschau im Admin erscheint sofort nach Upload (über `/file`-Endpoint, unabhängig von IIIF-Status).
Batch-Medienimport (ZIP + CSV/TSV-Mapping) ist im Importer-Wizard als `StepMedia.tsx` implementiert.

### Phase 6 – Admin-UI ✅ (mit Lücken)
Alle 4 Typen: Listen-Screen + Formular (dynamisch aus Schema, wiederholbare Felder, Status-Selector).
Login-Screen, JWT-Token in localStorage, automatischer Logout bei 401.
Schema-Editor: interner Feldname wird automatisch aus Label DE als Slug befüllt.
Vokabular-Verwaltung vollständig verdrahtet.

**Noch offen in Phase 6:**
- ~~Relationen-Panel im Formular (Phase 6.1)~~ ✅ – Relation-Metadaten bearbeiten, Gegenrichtung anzeigen
- ~~Snapshot-UI im Formular (Phase 7)~~ ✅ – Snapshots anzeigen, erstellen und wiederherstellen
- ~~Benutzer-Verwaltungs-Screen~~ ✅ – User-CRUD vollständig (Liste, Anlegen, Rolle ändern, Deaktivieren, Löschen, Zugangsdaten, API-Keys)

### Phase 6.2 – Mobile Admin-Optimierung ⚠️ – Issue #253

**Ziel:** Admin-Kernfunktionen auf Smartphones und Tablets möglichst vollständig nutzbar machen, ohne separate Mobile-UI.

**Erledigt (v0.5.1):**
- Produkt- und Designkontext in `PRODUCT.md`, `DESIGN.md` und `DESIGN.json`
- Responsive App-Shell bei ≤768 px
- Sidebar als Drawer mit Overlay und 44-px-Touchzielen
- Kompakte Topbar für Navigation, globale Suche und Benutzeraktion
- Playwright-Regressionstest für Öffnen und Schließen bei 319 × 359 px
- E2E-Runner nutzt Compose-API über den bestehenden Vite-Proxy
- Login-, Objektanlage-, Medienupload- und Mobile-Navigationstests laufen wieder vollständig

**Nächste Session, Reihenfolge:**
1. Globale Mobile-Regeln für Seitenheader, Toolbars, Tabs, Tabellen und Pagination
2. Schema-Screen: Subtypen-Auswahl statt fester 220-px-Spalte; Feldzeilen mobil reduzieren
3. Record-Formulare: Aktionsleiste umbrechen; Datums-, Geo- und weitere Inline-Grids stapeln
4. Restliche Admin-Screens bei 319 px, 375 px und Tablet prüfen
5. Playwright-Screenshots und Regressionstests ergänzen

**Bekannte Test-Infrastruktur-Lücke:**
- Admin-`lint`-Script findet `eslint` nicht, weil Dependency fehlt

### Phase 7 – Elasticsearch + Versionierung ✅
Elasticsearch-Integration: Index beim Create/Update/Delete, `/v1/search`-Endpoint mit Facetten.
ES-Facetten für vocab- und authority-Felder funktionieren korrekt (Label wird extrahiert, nicht das Raw-Objekt).
Snapshot-UI im Admin-Formular für alle 4 Typen vollständig ✅ (Issue #217, 2026-05-29).
Robuste ES-Indexierung via Celery-Retry, manueller Reindex, Index-Health und Reconciliation-Job vollständig ✅ (Issue #214, 2026-06-26).

### Phase 8 – Public-Portal ✅ (mit laufenden Verbesserungen)
Homepage, Suchergebnisse, alle 4 Detailseiten, Theme-System.
Portal-Container liefert Static Files korrekt aus, nginx proxied `/v1/` zum API.
Windowed Pagination mit Ellipsis in Suchergebnissen.

**Neu seit 2026-05-06:**
- Markdown-Rendering in StaticPageView (marked + DOMPurify, #72)
- Karte auf PlaceDetailPage (OSM-iframe, #73)
- OpenGraph/Meta-Tags auf allen Detailseiten (react-helmet-async, #74)
- IIIF `link:alternate` im `<head>` auf ObjectDetailPage (#75)
- Relation-Facetten beim Objekt-Browsing (denormalisiert in ES, #83)
- Relation-Type-Labels aus Vokabular aufgelöst in Admin-UI ✅ (#78)
- IIIF-Viewer mit Clover IIIF und Cantaloupe-Tiles End-to-End verdrahtet ✅

### Phase 9 – Authority-Plugin-System ✅
6 Adapter implementiert: GND (lobid.org), Geonames, VIAF, Wikidata, Getty TGN (SPARQL), ICONCLASS.
Abstrakte Basisklasse `AuthoritySource(ABC)`, DB-Registry mit Lazy Loading, Cache-Invalidierung.
Endpoints: `GET /v1/authorities/`, `/v1/authorities/search`, `/v1/authorities/fetch`.
41 Unit-Tests (Adapter + Service-Layer) vollständig grün.
Normdaten auch an Vokabultermen: `metadata.authorities` (mehrere pro Term), Autocomplete im Term-Editor, CSV-Import mit Source-Dropdown (v0.3.7, #258). `AuthorityInput` in `frontend/admin/src/components/AuthorityInput.tsx` geteilt.

**Noch offen:**
- (keine – Authority-Source ist bereits an `AuthorityInput` durchgereicht)

### Phase 10 – Importer-Wizard ✅
Vollständiger 4-Schritte-Wizard: Upload → Mapping → Dry Run → Import.
Formate: CSV, TSV, Excel (.xlsx/.xls), XML.
Transforms: split, replace, regex_extract, trim, vocab_map, expression.
Dry Run mit Vorschau, Warnungen, Heterogenitätserkennung.
Import als Celery-Task mit Fortschrittsanzeige + ETA.
Portable Import-Profile (JSON-Export/-Import).
Automatische Vokabular-Term-Anlage beim Import.
localStorage-Persistenz: Mapping + Options bleiben erhalten, Rows werden nicht gespeichert.

**Noch offen in Phase 10:**
- Auto-Mapping-Heuristik: Levenshtein + Synonymtabelle (#199)
- 10-Zeilen-Vorschau-Import mit Rollback (#201)
- Diff-Preview bei Upsert (#202)
- Streaming-Upload für Dateien > 10 MB (#204)

### Phase 10.1 – Batch-Medienimport ✅
ZIP-Archiv mit Bildern + CSV/JSON-Mapping-Datei (Dateiname → Objekt-ID + media_type).
Celery-Task für asynchrone Verarbeitung, Fortschritts-Anzeige im Admin.
Wiederverwendet Vokabular "media_types" für Typ-Mapping.
UI im Importer-Wizard (`StepMedia.tsx`) vorhanden.

### Phase 11 – OAI-PMH ✅
Endpoint `/v1/oai` vorhanden. OAI-PMH nutzt die generische Export-Mapping-Schicht.
ListSets, ResumptionToken, GetRecord, `badResumptionToken` und OAI-Tests sind implementiert; bei ES-Ausfällen liefert der Endpoint `503` mit `Retry-After`.

### Phase 11.1 – Export-Mapping für OAI-PMH ✅ – Issue #225
**Umsetzung:** Generische `metadata_mappings`-Tabelle + `/v1/metadata-mappings` API + Export-Abschnitt im Schema-Editor.

**Aktueller Stand:**
- `oai_dc` nutzt die Mappings als ersten Consumer
- LIDO und METS/MODS sind im UI als Stubs vorbereitet
- Das Mapping bleibt formatneutral und kann spaeter von weiteren Exportern wiederverwendet werden

### Phase 12 – Hardening ⚠️
- Rate Limiting ✅ – `/v1/search`, `/v1/oai` auf 100/min; `/v1/authorities/search`, `/v1/authorities/fetch` auf 60/min (Issue #219, geschlossen).
- Verwaiste Relationen ✅ – `delete_relations()` + `cleanup_relation_refs` Celery-Task auf allen 4 Typen (Issue #149, geschlossen).
- Produktions-Secrets ✅ – Startup-Guard in `main.py` verweigert Start wenn `SECRET_KEY` Default/zu kurz oder `DEFAULT_ADMIN_PASSWORD` ein bekanntes Default ist (Issue #20, geschlossen).
- Deep `/health` ✅ – prüft Postgres + Elasticsearch aktiv, liefert 503 bei Degradation (v0.5.9, Production-Readiness-Audit).
- Backup-Automatisierung ✅ – `backup`-Compose-Service (`docker/backup.sh`): tägliches `pg_dump` + Media-tar, Retention, konfigurierbar via `.env` (an/aus, Uhrzeit/Intervall); Restore-Drill real durchgespielt (Issue #273, v0.5.10/v0.5.11).
- Optimistic Locking ✅ – `version`-Spalte + `If-Match` + 409 auf allen 5 Typen, feldweiser 3-Wege-Merge in der Admin-UI (Issue #272, v0.6.0).
- Broker-Resilienz ✅ – Redis-Ausfall bricht keine schreibenden Requests mehr; `workers/enqueue.py` (fire-and-forget schluckt, Job-ID-Pfade 503) (Issue #274, v0.6.2).
- nginx TLS-Terminierung (Infra, deployment-spezifisch)
- Perf-Tests (locust)
- OpenAPI-Dokumentation finalisieren
- Cantaloupe-Health-Check beim Start ✅ – `_check_cantaloupe_health()` in `main.py` pingt `/iiif/3` beim Lifespan-Start, loggt Warning bei Fehlern

### Phase 14 – Procedure-Typ (Leihverkehr, Erwerbung, Restaurierung) ✅ – Issue #238

**Umsetzung:** Gemerged in `main` via `feat/procedures` (Tags `v0.2.0`–`v0.2.5`, Merge `6dd01d6`).

5. Primärtyp für transaktionale/prozessuale Vorgänge. Semantisch getrennt von Occurrence (FRBR).

**Erledigt:**
- Tabelle `procedures` mit `procedure_type`, `status`, Datumsfeldern, `reference_number`, `metadata_` und Snapshots/Audit-Log
- `collection_status` auf Objekten mit Public-Search-Guard via Elasticsearch/Visibility-Layer
- CRUD-API `/v1/procedures`, Completion-Endpoint `/v1/procedures/{id}/complete`, Filter für Typ, Status, Fälligkeit, Referenznummer und Suche
- Schema-Engine akzeptiert `procedure` plus eingebaute Vorgangstypen als `target_subtype`
- Relationen zwischen Vorgängen und Objekten über bestehende `relations`-Tabelle; Objekt-Panel im Vorgangsformular und Vorgangs-Panel im Objektformular
- Validierung gegen zweite aktive `loan_out`-Leihgabe pro Objekt im Service/API-Layer
- Admin-UI: Vorgangsliste, Vorgangsformular, Vorgangstypen, Abschlussdialog, Objektstatus-Vorschlag, Schnellfilter für überfällige aktive Vorgänge
- Dokumentation in `docs/konzept-vorgaenge.md` und Produktionshinweis zum Reindex in `docs/04_produktion.md`
- Tests: `backend/tests/integration/test_procedures_integration.py`, `backend/tests/integration/test_schema_container_fields.py`, `backend/tests/test_search_visibility.py`

**Zurückgestellt auf Post-MVP:** Per-Objekt strukturierte Zusatzfelder auf Vorgangs-Relationen (Issue #239), Status-Transition-Guards, Auto-Referenznummern, Datei-Attachments.

---

## Offene Phasen

### Phase 8.1 – Facettiertes Browsing + Portal-Konfiguration
**Ziel:** Sammlungsverantwortliche konfigurieren im Admin, welche Facetten und Felder im Portal sichtbar sind.

Konzept:
- Admin-Screen "Portal-Einstellungen": Welche Felder erscheinen in der Ergebnisliste? Welche Felder sind Facetten?
- Konfiguration in DB (`portal_config` Tabelle oder JSONB in `authority_sources`)
- Portal liest Konfiguration beim Start via `/v1/theme`
- Elasticsearch-Mapping wird entsprechend erweitert

Dateien (neu):
- `backend/src/katalon/api/v1/portal_config.py`
- `frontend/admin/src/components/screens/ScreenPortalConfig.tsx`
- `frontend/portal/src/hooks/usePortalConfig.ts`

---

### Phase 13 – Inherited Fields (ES-Denormalisierung) – Issue #213
Felder verlinkter Records werden beim ES-Indexieren eingebettet, damit sie bei verknüpften Objekten suchbar und facettierbar sind (z.B. Erscheinungsjahr eines verknüpften Werks).
Kaskaden-Reindex bei Änderungen am verlinkten Record, max. 1 Ebene tief.
Siehe Memory: `project_inherited_fields.md`.

---

## Bekannte technische Schulden

Diese Punkte blockieren keine Feature-Arbeit, sollten aber vor einem öffentlichen Release adressiert werden.

### Fehlerbehandlung & Observability

**ES-Fehler werden geloggt ✅** – Alle vier CRUD-Module (`objects.py`, `entities.py`, `places.py`, `occurrences.py`) loggen ES-Indexierungs-Fehler mit `logger.warning("ES index/remove failed", exc_info=True)`.

**Kein Logging in API-Modulen** – Nur `pids.py` und `main.py` haben `logging` konfiguriert. Alle anderen API-Module loggen nichts.
→ `logger = logging.getLogger(__name__)` in alle Module; Fehler, Validierungsmisserfolge und Async-Task-Queuing loggen.

### Datenintegrität

**Hardcodierte Vokabular-Namen** – Die Strings `"media_types"` und `"relation_types"` tauchen in mehreren Dateien auf (workers, API, Frontend). Bei Umbenennung brechen Features still.
→ In `config.py` als Konstante extrahieren.

### Test-Lücken

| Feature | Status |
|---|---|
| ES-Indexierung + Suche (End-to-End) | ⚠️ Teiltests für Visibility vorhanden, kein echtes ES-E2E |
| Relationen erstellen/traversieren | ⚠️ Service-/Validierungstests vorhanden, UI-E2E fehlt |
| Snapshot erstellen/wiederherstellen | ❌ keine Tests |
| Media-Upload-Workflow + IIIF-Manifest | ✅ 19 Unit-Tests (Cantaloupe, Tasks, API) |
| Procedure-Workflows | ✅ Integrationstests für CRUD, aktive `loan_out`-Sperre und Schema-Subtypen |
| OAI-PMH ResumptionToken Roundtrip | ❌ keine Tests |

---

## Nächste Schritte (Reihenfolge)

### Beta-Blocker – alle erledigt ✅

~~1. Rate-Limiting~~ ✅ Issue #219
~~2. Snapshot-UI~~ ✅ Issue #217
~~3. Verwaiste Relationen~~ ✅ Issue #149
~~4. Production Hardening: Secrets~~ ✅ Issue #20

### MVP-Pflicht (vor oder gleichzeitig mit Beta)

1. Inherited Fields: Denormalisierte Relationsfelder im ES-Index (Phase 13) – Issue #213
2. ~~Robuste ES-Indexierung: Retry, Reconciliation, Health (Phase 7)~~ ✅ Issue #214

### Nachrangig (Post-Beta)

3. Importer-UX: Auto-Mapping (#199), 10-Zeilen-Vorschau (#201), Diff-Preview (#202), Streaming-Upload (#204)
4. Phase 12 Resthardening: TLS-Terminierung, locust, OpenAPI

---

## Teststrategie

| Ebene | Tool | Wann |
|---|---|---|
| Unit | pytest + hypothesis | Jeder Push |
| Integration | pytest + testcontainers-python | Jeder Push |
| E2E Backend | pytest + httpx AsyncClient | main branch |
| E2E Frontend | Playwright | main branch |
| Performance | locust | Vor Release |

---

## Bekannte Risiken

| Risiko | Mitigation |
|---|---|
| JSONB-Queries langsam | GIN-Index auf `metadata` |
| Celery-Fehler schwer debugbar | Flower-Dashboard, dead-letter Queue, Retry-Limit |
| ES-Mappings brechen bei Schema-Änderungen | Index-Aliase + Zero-Downtime-Reindex |
| Cantaloupe-Tile-Generierung verdrahtet ✅ | Celery-Task `generate_iiif_tiles` ruft Cantaloupes `info.json` auf; Tests vorhanden |
| ES-Indexfehler geloggt ✅ | `logger.warning()` in allen 4 CRUD-Modulen; `X-Search-Index: failed` Header optional |
