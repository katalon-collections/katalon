# Katalon – Implementierungsplan

## Stand: 2026-05-16

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

### Phase 3 – CRUD alle 4 Typen ✅
REST-Endpoints für Objects, Entities, Places, Occurrences, Relationen.
Pagination, Status-Filter, Fulltext-Suche (PostgreSQL `search_vector`).

### Phase 4 – Auth + Audit Log ✅
JWT-Auth (jose), Rollen (admin/editor/viewer), bcrypt (direkt, ohne passlib).
Default-Admin-User wird beim ersten Start angelegt (`admin@katalon.dev / admin`).
Audit Log bei jedem Create/Update/Delete.

### Phase 5 – Media ✅ / IIIF ⚠️
Upload (Single-File), Celery-Task, Speicherung. IIIF-Manifest-Endpoint vorhanden.
`media_type`-Feld pro Datei; konfigurierbare Typen via Vokabular "media_types" (Vorderseite, Rückseite, Detail …).
Cantaloupe-Integration für Tile-Generierung noch nicht verdrahtet (Endpoint antwortet, produziert aber keine echten IIIF-Tiles).

**Noch offen in Phase 5:**
- Batch-Medienimport (ZIP oder Ordner mit CSV-Mapping → Phase 10.1)
- PATCH-Endpoint für `media_type` + `is_primary` ✅ (implementiert)

### Phase 6 – Admin-UI ✅ (mit Lücken)
Alle 4 Typen: Listen-Screen + Formular (dynamisch aus Schema, wiederholbare Felder, Status-Selector).
Login-Screen, JWT-Token in localStorage, automatischer Logout bei 401.
Schema-Editor, Vokabular-Verwaltung vollständig verdrahtet.

**Noch offen in Phase 6:**
- Importer-Wizard (ScreenImporter ist Stub – Phase 10)
- Relationen-Panel im Formular (Phase 6.1)
- Snapshot-UI im Formular (Phase 7)
- Benutzer-Verwaltungs-Screen (Placeholder – nur API-Key-Verwaltung vorhanden, kein User-CRUD)

### Phase 7 – Elasticsearch + Versionierung ⚠️
Elasticsearch-Integration: Index beim Create/Update/Delete, `/v1/search`-Endpoint mit Facetten.
Snapshot-Endpoints im Backend vorhanden.

**Noch offen:**
- Snapshot-UI in Admin-Formular (Knopf + Versionsliste)
- Re-Index-Task via Celery (Massenreindex bei Schema-Änderungen)

### Phase 8 – Public-Portal ✅ (mit laufenden Verbesserungen)
Homepage, Suchergebnisse, alle 4 Detailseiten, Theme-System.
Portal-Container liefert Static Files korrekt aus, nginx proxied `/v1/` zum API.

**Neu seit 2026-05-06:**
- Markdown-Rendering in StaticPageView (marked + DOMPurify, #72)
- Karte auf PlaceDetailPage (OSM-iframe, #73)
- OpenGraph/Meta-Tags auf allen Detailseiten (react-helmet-async, #74)
- IIIF `link:alternate` im `<head>` auf ObjectDetailPage (#75)
- Relation-Facetten beim Objekt-Browsing (denormalisiert in ES, #83)
- Relation-Type-Labels aus Vokabular aufgelöst in Admin-UI ✅ (#78 – `ScreenForm.tsx:1309`)

**Noch offen:**
- IIIF-Viewer (Cantaloupe-Tiles noch nicht End-to-End verdrahtet)
- „Zurück zur Suche" auf Detailseiten (#77, post-mvp)

---

## Offene Phasen

### Phase 6.1 – Relationen-Panel im Admin-Formular
Suche über alle Typen, Relationstyp wählen, Metadaten auf der Relation.
Endpoint `/v1/relations` ist fertig, UI-Grundgerüst vorhanden (Liste + Hinzufügen-Dialog).

**Offen:**
- Bearbeitung von Relation-Metadaten (JSONB-Felder auf der Relation selbst)
- Darstellung der Gegenrichtung (from/to korrekt anzeigen wenn Datensatz `to_id` ist)

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

### Phase 9 – Authority-Plugin-System ✅
6 Adapter implementiert: GND (lobid.org), Geonames, VIAF, Wikidata, Getty TGN (SPARQL), ICONCLASS.
Abstrakte Basisklasse `AuthoritySource(ABC)`, DB-Registry mit Lazy Loading, Cache-Invalidierung.
Endpoints: `GET /v1/authorities/`, `/v1/authorities/search`, `/v1/authorities/fetch`.
41 Unit-Tests (Adapter + Service-Layer) vollständig grün.

**Noch offen:**
- Admin-UI: Autocomplete-Feld bei der Erfassung (authority-Felder im Formular)
- Admin-UI: `authority_source` aus Schema wird in `ScreenForm` nicht an `AuthorityInput` weitergegeben – alle Authority-Suchen laufen aktuell gegen den hardcodierten Fallback (`ScreenForm.tsx` ~1030)

### Phase 10 – Importer-Wizard
4-Schritte-Wizard: Upload → Mapping → Dry Run → Import.
Backend-Endpoint `/v1/importer` vorhanden (Stub).
Admin-UI: ScreenImporter ist Stub.

### Phase 10.1 – Batch-Medienimport
ZIP-Archiv mit Bildern + CSV/JSON-Mapping-Datei (Dateiname → Objekt-ID + media_type).
Celery-Task für asynchrone Verarbeitung, Fortschritts-Anzeige im Admin.
Wiederverwendet Vokabular "media_types" für Typ-Mapping.

### Phase 11 – OAI-PMH
Endpoint `/v1/oai` vorhanden. Dublin-Core-Mapping für Objects.

**Offen:**
- ListSets
- ResumptionToken für große Collections (Pagination)
- Spezifische Fehlerbehandlung: Aktuell wird bei jedem Fehler (inkl. ES-Timeout) `noRecordsMatch` zurückgeliefert (`oai.py:134, 176, 203`). Harvester können transiente von permanenten Fehlern nicht unterscheiden.
- Tests für Token-Roundtrips und Pagination-Edge-Cases

### Phase 12 – Hardening
- Rate Limiting: slowapi ist eingebunden, aber **keine einzige Route ist dekoriert** (`main.py`). Öffentliche Endpunkte (`/v1/search`, `/v1/oai`, `/v1/authorities/search`) müssen noch begrenzt werden.
- Produktions-Secrets (kein `dev-secret-key` in Prod)
- nginx TLS-Terminierung
- Perf-Tests (locust)
- OpenAPI-Dokumentation finalisieren
- Cantaloupe-Health-Check beim Start (fehlende Konfiguration wird sonst erst beim ersten Upload sichtbar)

---

## Bekannte technische Schulden

Diese Punkte blockieren keine Feature-Arbeit, sollten aber vor einem öffentlichen Release adressiert werden.

### Fehlerbehandlung & Observability

**ES-Fehler werden still verschluckt** – Alle vier CRUD-Module (`objects.py`, `entities.py`, `places.py`, `occurrences.py`) fangen ES-Indexierungs-Fehler mit `except Exception: pass`. Datensätze werden in der DB gespeichert, sind aber nicht durchsuchbar; der User bekommt kein Feedback.
→ Mindestens per `logger.exception()` loggen; idealerweise `X-Search-Index: failed` Header zurückgeben.

**Kein Logging in API-Modulen** – Nur `pids.py` und `main.py` haben `logging` konfiguriert. Alle anderen API-Module loggen nichts.
→ `logger = logging.getLogger(__name__)` in alle Module; Fehler, Validierungsmisserfolge und Async-Task-Queuing loggen.

### Datenintegrität

**Naive Datetimes** – `models.py:26` verwendet `datetime.utcnow()` (naive, kein Timezone-Info). Alle OAI-PMH-Timestamps und ES-Datumsfilter bauen darauf auf.
→ Ersetzen durch `datetime.now(timezone.utc)`.

**Hardcodierte Vokabular-Namen** – Die Strings `"media_types"` und `"relation_types"` tauchen in mehreren Dateien auf (workers, API, Frontend). Bei Umbenennung brechen Features still.
→ In `config.py` als Konstante extrahieren.

### Test-Lücken

| Feature | Status |
|---|---|
| ES-Indexierung + Suche (End-to-End) | ❌ keine Tests |
| Relationen erstellen/traversieren | ❌ nur Auth-Tests |
| Snapshot erstellen/wiederherstellen | ❌ keine Tests |
| Media-Upload-Workflow + IIIF-Manifest | ❌ keine Tests |
| OAI-PMH ResumptionToken Roundtrip | ❌ keine Tests |

---

## Nächste Schritte (Reihenfolge)

1. **Jetzt:** Authority-`source`-Parameter in `ScreenForm` an `AuthorityInput` durchreichen (`ScreenForm.tsx` ~1030)
2. Admin-UI: Benutzer-Verwaltungs-Screen (User-CRUD, Rollen, Deaktivierung) – `ScreenUsers.tsx` ist aktuell nur API-Key-Verwaltung
3. Relationen-Panel im Admin-Formular vervollständigen (Phase 6.1 – Relation-Metadaten bearbeiten)
4. Snapshot-UI im Admin-Formular (Phase 7)
5. ES-Fehler loggen statt verschlucken (technische Schuld – kleiner Aufwand, hoher Nutzen)
6. Rate-Limiting-Dekoratoren auf `/v1/search`, `/v1/oai`, `/v1/authorities/search` (Phase 12)
7. Batch-Medienimport (Phase 10.1)
8. Cantaloupe Tile-Generierung End-to-End (Issue #13)

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
| Cantaloupe-Tile-Generierung nicht verdrahtet | Celery-Task `generate_iiif_tiles` muss noch Cantaloupe-Derivate-API aufrufen |
| ES-Indexfehler unsichtbar | `except Exception: pass` in 12+ Endpoints ersetzen |
