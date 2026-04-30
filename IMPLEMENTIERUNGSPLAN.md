# Katalon – Implementierungsplan

## Phasenplan

### Phase 0 – Infra
**Ziel:** Alle Services laufen, sind erreichbar, Health-Checks grün.

Dateien:
- `docker-compose.yml` (api, worker, db, elasticsearch, redis, cantaloupe, admin, portal, nginx)
- `docker-compose.dev.yml` (Overrides: Hot-Reload, Ports exposed)
- `docker/Dockerfile.backend`
- `docker/Dockerfile.worker`
- `docker/Dockerfile.admin`
- `docker/Dockerfile.portal`
- `backend/pyproject.toml` (uv-managed, FastAPI, SQLAlchemy, Alembic, Celery, …)
- `backend/src/katalon/config.py` (Pydantic Settings, aus ENV)
- `backend/src/katalon/main.py` (FastAPI factory, Health-Endpoint)

---

### Phase 1 – Core-Datenbank
**Ziel:** Alle 4 Primärtypen + Relationen + Hilfstabellen als ORM-Models, erste Migration läuft.

Dateien:
- `backend/src/katalon/database.py` (SQLAlchemy async engine, session factory)
- `backend/src/katalon/core/models.py` (alle ORM-Models – siehe unten)
- `backend/migrations/` (Alembic init + erste Migration)

**ORM-Models:**
```python
# Alle 4 Primärtypen haben dieselbe Grundstruktur
objects      (id, idno, status, metadata JSONB, search_vector, created_at, updated_at)
entities     (id, entity_type, status, metadata JSONB, search_vector, created_at, updated_at)
places       (id, geom GEOMETRY, status, metadata JSONB, search_vector, created_at, updated_at)
occurrences  (id, occurrence_type, status, metadata JSONB, search_vector, created_at, updated_at)

# Schema
field_definitions (id, target_type, name, label JSONB, field_type,
                   is_required, is_repeatable, sort_order, settings JSONB)

# Vokabulare
vocabularies      (id, name, is_hierarchical)
vocabulary_terms  (id, vocabulary_id, term, label JSONB, parent_id)

# Relationen (generisch)
relations (id, from_type, from_id, to_type, to_id, relation_type, metadata JSONB, created_at)

# Medien
media_files (id, object_id, filename, mime_type, file_path, iiif_manifest JSONB, status)

# Audit + Snapshots
audit_log        (id, record_type, record_id, user_id, action, changed_fields JSONB, created_at)
record_snapshots (id, record_type, record_id, label, snapshot JSONB, created_by, created_at)

# Authority-Quellen
authority_sources (id VARCHAR, label, adapter_class, config JSONB, is_enabled)

# Auth
users (id, email, hashed_password, role, is_active, created_at)
```

---

### Phase 2 – Schema-Engine
**Ziel:** Admins können Felder für jeden Typ definieren. Vokabulare verwaltbar.

Dateien:
- `backend/src/katalon/services/schema_service.py`
  - `validate_metadata(record_type, metadata_dict)` – prüft gegen field_definitions
  - `get_field_definitions(record_type)` – cached
- `backend/src/katalon/api/v1/schema_admin.py` – CRUD für field_definitions
- `backend/src/katalon/api/v1/vocabularies.py` – CRUD für vocabularies + terms
- `backend/src/katalon/core/schemas.py` – Pydantic I/O-Schemas

**Besonderheit Wiederholbare Felder:**
```python
# schema_service validiert: ist Feld repeatable?
# Wenn ja: Wert muss Liste sein
# Wenn nein: Wert muss skalarer Typ sein
```

---

### Phase 3 – CRUD alle 4 Typen + Relationen
**Ziel:** Vollständige REST-Endpoints für Objects, Entities, Places, Occurrences + Relationen.

Dateien:
- `backend/src/katalon/services/object_service.py`
- `backend/src/katalon/services/entity_service.py`
- `backend/src/katalon/services/place_service.py`
- `backend/src/katalon/services/occurrence_service.py`
- `backend/src/katalon/services/relation_service.py`
- `backend/src/katalon/api/v1/objects.py`
- `backend/src/katalon/api/v1/entities.py`
- `backend/src/katalon/api/v1/places.py`
- `backend/src/katalon/api/v1/occurrences.py`
- `backend/src/katalon/api/v1/relations.py`

**Endpoints-Muster (gleich für alle 4 Typen):**
```
GET    /v1/objects          – Liste, Pagination, Filter
POST   /v1/objects          – Anlegen (metadata wird gegen Schema validiert)
GET    /v1/objects/{id}     – Detail inkl. Relationen
PUT    /v1/objects/{id}     – Update (Audit Log wird geschrieben)
DELETE /v1/objects/{id}
POST   /v1/objects/{id}/snapshot – Snapshot speichern
GET    /v1/objects/{id}/snapshots
```

---

### Phase 4 – Auth + Audit Log
**Ziel:** JWT-Auth, Rollen (admin/editor/viewer), Audit Log wird bei jedem Update geschrieben.

Pakete: `fastapi-users[sqlalchemy]`

Dateien:
- `backend/src/katalon/core/dependencies.py` (current_user, require_role)
- `backend/src/katalon/api/v1/auth.py`
- `backend/src/katalon/services/audit_service.py`
  - `log_change(record_type, record_id, user_id, action, old, new)`
  - Wird in allen Services aufgerufen, nicht in Endpoints

---

### Phase 5 – Media & IIIF
**Ziel:** Bilder hochladen → Celery verarbeitet → Cantaloupe liefert IIIF-Tiles → Manifest abrufbar.

Dateien:
- `backend/src/katalon/api/v1/media.py`
- `backend/src/katalon/services/media_service.py`
- `backend/src/katalon/workers/media_tasks.py`
  - `generate_iiif_tiles.delay(media_file_id)` – ruft Cantaloupe-Derivate-API
  - `build_iiif_manifest(media_file_id)` – schreibt IIIF Manifest 3.0
- `backend/src/katalon/integrations/cantaloupe.py`

---

### Phase 6 – Admin-UI (React)
**Ziel:** Arbeitsfähige Eingabeoberfläche für alle 4 Typen.

Screens (siehe `design-prompts/02_admin_ui.md`):
1. Listen-Ansicht (pro Typ)
2. Erfassungsformular (dynamisch aus field_definitions gerendert)
3. Schema-Editor
4. Vokabular-Verwaltung

Dateien:
- `frontend/admin/src/api/` – OpenAPI-generierter Client
- `frontend/admin/src/components/DynamicForm/` – rendert Felder aus Schema
- `frontend/admin/src/components/RelationPanel/`
- `frontend/admin/src/components/MediaUpload/`

---

### Phase 7 – Elasticsearch + Versionierung
**Ziel:** Volltextsuche mit Facetten, Snapshots abrufbar.

Dateien:
- `backend/src/katalon/integrations/elasticsearch.py`
- `backend/src/katalon/services/search_service.py`
- `backend/src/katalon/workers/index_tasks.py` – Re-Index via Celery
- `backend/src/katalon/api/v1/search.py`

**Index-Strategie:** Index-Alias + Zero-Downtime-Reindex bei Schema-Änderungen.

---

### Phase 8 – Public-Portal (React)
Screens (siehe `design-prompts/01_discovery_portal.md`):
1. Homepage
2. Suchergebnisse (Facetten-Sidebar)
3. Objekt-Detail (IIIF-Viewer)
4. Orts-Detail (Karte)
5. Entitäts-Detail

---

### Phase 9 – Authority-Plugin-System
**Ziel:** Externe Normdaten (GND, VIAF, Geonames) in der Erfassung nutzbar.

Dateien:
- `backend/src/katalon/integrations/authority/base.py` – `AuthoritySource(ABC)`
- `backend/src/katalon/integrations/authority/gnd.py`
- `backend/src/katalon/integrations/authority/geonames.py`
- `backend/src/katalon/api/v1/authority.py` – `/v1/authority/search`, `/v1/authority/fetch`

---

### Phase 10 – Smart Importer

Wizard: Upload → Mapping → Dry Run → Import

Dateien:
- `backend/src/katalon/services/importer_service.py`
- `backend/src/katalon/api/v1/importer.py`
- `frontend/admin/src/components/Importer/` – Wizard UI

---

### Phase 11 – OAI-PMH

- `backend/src/katalon/api/v1/oaipmh.py` – Verbs: Identify, ListRecords, GetRecord, ListSets
- `backend/src/katalon/services/oaipmh_service.py` – Dublin Core Mapping

---

### Phase 12 – Hardening

- Rate Limiting (slowapi)
- nginx-Config (Reverse Proxy, Static Files)
- Perf-Tests (locust)
- OpenAPI-Dokumentation finalisieren

---

## Implementierungsreihenfolge (Dependency-Graph)

```
config + database
    └── core/models (alle 4 Typen)
            └── schema_service + vocabulary_service
                    └── object/entity/place/occurrence services
                            ├── auth + audit_service
                            ├── media_service → celery → cantaloupe
                            │       └── Admin-UI (React)
                            ├── search_service → ES
                            │       └── Public-Portal (React)
                            ├── authority adapters
                            ├── importer_service
                            └── oaipmh_service
```

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
| python-edtf unzureichend für alle Datumsvarianten | Custom Serializer als Wrapper vorbereiten |

---

## Offene Entscheidungen (vor Phase 6 klären)

- React-Router vs. TanStack Router für Admin-UI
- API-Client: OpenAPI-Codegen (`openapi-typescript-codegen`) vs. manuell
- Fuzzy-Datum UI-Komponente: Monat/Jahr/Präzisions-Selektor im Detail ausdesignen
