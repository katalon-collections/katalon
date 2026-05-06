# Katalon – Implementierungsplan

## Stand: 2026-05-06

---

## Erledigte Phasen

### Phase 0 – Infra ✅
Docker Compose: api, worker, db (PostGIS), elasticsearch, redis, cantaloupe, admin, portal, nginx.
`docker/nginx.static.conf` für statische SPA-Container; `docker/nginx.conf` als Reverse Proxy.

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
- Relationen-Panel im Formular (Placeholder – Phase 6.1)
- Snapshot-UI im Formular (Placeholder – Phase 7)
- Benutzer-Verwaltungs-Screen (Placeholder)

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

**Noch offen:**
- IIIF-Viewer (Cantaloupe-Tiles noch nicht End-to-End verdrahtet)
- „Zurück zur Suche" auf Detailseiten (#77, post-mvp)
- Relation-Type-Labels aus Vokabular (#78, post-mvp)

---

## Offene Phasen

### Phase 6.1 – Relationen-Panel im Admin-Formular
Suche über alle Typen, Relationstyp wählen, Metadaten auf der Relation.
Endpoint `/v1/relations` ist fertig, UI fehlt.

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

### Phase 9 – Authority-Plugin-System
GND, Geonames, VIAF. Adapter-Klasse `AuthoritySource(ABC)` im Backend vorhanden.
Endpoints `/v1/authority/search` und `/v1/authority/fetch` vorhanden, aber keine Adapter implementiert.
Admin-UI: Dropdown im Feld-Editor, Autocomplete bei der Erfassung.

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
Needs: ListSets, ResumptionToken für große Collections, Tests.

### Phase 12 – Hardening
- Rate Limiting (slowapi bereits eingebunden)
- Produktions-Secrets (kein `dev-secret-key` in Prod)
- nginx TLS-Terminierung
- Perf-Tests (locust)
- OpenAPI-Dokumentation finalisieren

---

## Nächste Schritte (Reihenfolge)

1. **Jetzt:** Daten erfassen → erste echte Objekte anlegen, Elasticsearch-Index befüllen
2. **Danach:** Facettiertes Browsing im Portal fertigstellen (Filter greifen auf ES-Facetten)
3. Portal-Konfiguration (welche Felder sichtbar)
4. Relationen-Panel im Admin
5. Snapshot-UI
6. Importer-Wizard

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
