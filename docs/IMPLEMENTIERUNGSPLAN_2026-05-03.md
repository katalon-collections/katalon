# Katalon – Implementierungsplan

## Stand: 2026-05-03

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
- Benutzer-Verwaltungs-Screen (Placeholder → Issue #43)
- Bildansicht/Preview nach Upload fehlt → Issue #49
- Hilfe- und Benachrichtigungs-Symbole ausblenden → Issue #46
- Suche im Admin-Backend nicht funktional → Issue #45

### Phase 7 – Elasticsearch + Versionierung ⚠️
Elasticsearch-Integration: Index beim Create/Update/Delete, `/v1/search`-Endpoint mit Facetten.
Snapshot-Endpoints im Backend vorhanden.

**Noch offen:**
- Snapshot-UI in Admin-Formular (Knopf + Versionsliste)
- Re-Index-Task via Celery (Massenreindex bei Schema-Änderungen)

### Phase 8 – Public-Portal ⚠️
Homepage, Suchergebnisse, Objekt-Detail-Seite an echte API verdrahtet.
Portal-Container liefert Static Files korrekt aus, nginx proxied `/v1/` zum API.

**Noch offen – Priorität hoch:**
- **Facettiertes Browsing**: Elasticsearch liefert Facetten (`by_type`, `by_status`), aber die Filterfunktion im Portal ist noch nicht vollständig (Typ-Filter existiert, Datums- und Metadaten-Facetten fehlen) → Issue #15
- **Portal-Konfiguration**: Welche Felder in Suchergebnissen/Detailseite erscheinen, ist hardcodiert. Admin-seitige Konfigurationsmöglichkeit (`/v1/theme`) existiert im Backend, aber keine UI.
- IIIF-Viewer (Placeholder – wartet auf Cantaloupe-Tiles) → Issue #52
- Entitäts-Detail-Seite → Issue #54
- Orts-Detail-Seite (mit Karte) → Issue #54
- Portal-Suche grundsätzlich nicht funktional → Issue #53
- Alle 4 Typen im Portal durchsuchbar → Issue #54
- Detailansicht: Feldbezeichner statt Labels, schlechtes Layout → Issue #55
- Generell zu wenig Padding im Portal → Issue #56
- Statische Seiten nicht anzeigbar → Issue #57

---

## Offene Phasen

### Phase 4.1 – Benutzerverwaltungs-Screen + Katalogisierer-Rolle (Issue #43)
Vollständiger CRUD-Screen für Benutzer im Admin.
Neue Rolle `cataloger`: Inhalte anlegen/bearbeiten, kein Zugriff auf Schema/Vokabular.
Nice to have: Katalogisierer darf nicht löschen, nur deaktivieren.

### Phase 6.1 – Relationen-Panel im Admin-Formular (Issue #47)
Suche über alle Typen, Relationstyp wählen (aus Vokabular `relation_types`), Metadaten auf der Relation.
Endpoint `/v1/relations` ist fertig, UI fehlt.
Label im Formular: "Beziehung zu Ort/Occurrence/Entität" statt statischem "Beziehung zu Ort".

### Phase 6.2 – Admin Quick-Fixes (Issues #44, #45, #46, #49, #50, #51)
Gebündelte kleinere Korrekturen:
- Einstellungen-Screen (Minimalimplementierung) → #44
- Admin-Suche reparieren → #45
- Hilfe/Notifications ausblenden → #46
- Bildvorschau (MediaGallery-Komponente) im Formular → #49
- Audit Log: Benutzername + Bindung an Datensatz → #50
- Frontend-Validierung Datumsfelder → #51

### Phase 6.3 – Schema-Erweiterungen (Issue #48)
- Regex-Validierung für Felder (`validation_regex` in `field_definitions.settings`)
- Backend-Validierung in `schema_service.validate_metadata()`
- Schema-Editor: Eingabefeld für regulären Ausdruck

### Phase 8.0 – Portal-Basisfixes (Issues #52, #53, #54, #55, #56, #57)
Vor dem facettierten Browsing müssen grundlegende Dinge funktionieren:
- IIIF-Viewer einbetten (OpenSeadragon oder Clover IIIF) → #52
- Portal-Suche grundsätzlich reparieren → #53
- Alle 4 Primärtypen im Portal durchsuchbar + Detailseiten → #54
- Detailansicht: lokalisierte Labels statt Feldnamen → #55
- Globales Padding-Review im Portal → #56
- Statische Seiten-Route im Portal → #57

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

### Phase 9.2 – DataCite-Integration + URN-API-Adapter (Post-MVP)
DOI-Vergabe via DataCite REST API → Issue #58
URN-Vergabe via DNB URN-Granular-API → Issue #59
Beide setzen Feldtyp `pid` (Issue #25) voraus.

### Phase 12 – Hardening
- Rate Limiting (slowapi bereits eingebunden)
- Produktions-Secrets (kein `dev-secret-key` in Prod)
- nginx TLS-Terminierung
- Perf-Tests (locust)
- OpenAPI-Dokumentation finalisieren

---

## Nächste Schritte (Reihenfolge)

> **Oberste Priorität:** Präsentationsoberfläche (Public Portal) muss zumindest rudimentär gut funktionieren, bevor weitere Features folgen.

1. **Phase 8.0 – Portal-Basisfixes** ← höchste Priorität: Suche, alle Typen, Layout, IIIF-Viewer (#52–#57)
2. **Phase 6.2 – Admin Quick-Fixes:** Hilfe/Notifications ausblenden, Admin-Suche, Bildvorschau, Audit Log (#44–#51)
3. **Phase 6.1 – Relationen-Panel:** Vokabular `relation_types`, Panel-UI, Label-Korrektur (#47)
4. **Phase 4.1 – Benutzerverwaltung:** Katalogisierer-Rolle, Verwaltungs-Screen (#43)
5. **Phase 6.3 – Regex-Validierung** (#48)
6. **Phase 8.1 – Facettiertes Browsing + Portal-Konfiguration**
7. Snapshot-UI (#14)
8. Importer-Wizard (Phase 10)

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
