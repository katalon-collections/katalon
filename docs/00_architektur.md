# Katalon – Systemarchitektur

## Überblick

Katalon ist ein Metadata Management System für den GLAM-Sektor. Die Architektur folgt einem klassischen API-First-Muster: ein Python-Backend liefert eine REST-API, zwei separate React-Frontends konsumieren sie.

```
                        ┌─────────────────────────────────┐
                        │           nginx (TLS)           │
                        │  example.org / admin.example.org│
                        └──────┬──────────────────┬───────┘
                               │                  │
                    ┌──────────▼──────┐   ┌────────▼────────┐
                    │  Portal (React) │   │  Admin  (React) │
                    │  public-facing  │   │  auth-required  │
                    │  port 4001 dev  │   │  port 4000 dev  │
                    └─────────────────┘   └─────────────────┘
                               │                  │
                    ┌──────────▼──────────────────▼────────┐
                    │         FastAPI (Python 3.12)        │
                    │       /v1/*  REST + OAI-PMH          │
                    │            port 8000 dev             │
                    └──┬──────────┬──────────┬─────────────┘
                       │          │          │
          ┌────────────▼─┐  ┌─────▼───┐  ┌──▼──────────────┐
          │  PostgreSQL  │  │  Redis  │  │ Elasticsearch 8 │
          │  + PostGIS   │  │ (Queue) │  │   (Volltext)    │
          └──────────────┘  └────┬────┘  └─────────────────┘
                                 │
                       ┌─────────▼──────────┐
                       │   Celery Worker    │
                       │  (Media, IIIF, RE) │
                       └─────────┬──────────┘
                                 │
                       ┌─────────▼──────────┐
                       │   Cantaloupe       │
                       │  IIIF Image API 3  │
                       └────────────────────┘
```

## Services im Detail

| Service | Image | Zweck | Persistenz |
|---|---|---|---|
| `api` | `python:3.12-slim` | FastAPI-App, alle REST-Endpoints | – |
| `worker` | gleich wie api | Celery-Worker (Medienverarbeitung, Reindex) | – |
| `db` | `postgres:16-alpine` | Primärer Datenspeicher (PostgreSQL + PostGIS) | Volume `db_data` |
| `redis` | `redis:7-alpine` | Celery-Broker und -Backend | – |
| `elasticsearch` | `elasticsearch:8` | Volltextsuche, OAI-PMH-Quelle | Volume `es_data` |
| `cantaloupe` | `islandora/cantaloupe` | IIIF Image API 3, Tile-Generierung | Volume `media_data` |
| `admin` | Node build → nginx | Admin-UI (React), port 4000 | – |
| `portal` | Node build → nginx | Public-Portal (React), port 4001 | – |
| `nginx` | `nginx:alpine` | Reverse Proxy, TLS (nur Produktion) | – |

## Backend-Struktur

```
backend/src/katalon/
├── main.py              # FastAPI-App, Router-Registrierung, CORS, Startup-Events
├── config.py            # Settings via Pydantic (aus .env)
├── database.py          # SQLAlchemy AsyncSession, SessionLocal
├── core/
│   ├── models.py        # SQLAlchemy ORM-Modelle (alle Tabellen)
│   ├── schemas.py       # Pydantic-Schemas (Request/Response)
│   └── dependencies.py  # FastAPI-Depends: get_current_user, require_role()
├── api/v1/              # HTTP-Handler (dünn: nur Routing + Validation)
│   ├── auth.py          # POST /token, POST /register
│   ├── objects.py       # CRUD Objekte + Medien-Endpoint
│   ├── entities.py      # CRUD Entitäten
│   ├── places.py        # CRUD Orte (PostGIS)
│   ├── occurrences.py   # CRUD Occurrences
│   ├── relations.py     # Generische Relationen
│   ├── schema_admin.py  # field_definitions CRUD
│   ├── vocabularies.py  # Vokabulare + Terme
│   ├── search.py        # Elasticsearch-Suche
│   ├── oai.py           # OAI-PMH (verb-Dispatch)
│   ├── oai_sets.py      # OAI-Sets CRUD
│   ├── authority.py     # Normdaten-Suche/Fetch
│   ├── users.py         # Benutzerverwaltung
│   ├── portal.py        # PortalConfig (Theme, Farben, Logo)
│   ├── pages.py         # Statische Seiten
│   ├── importer.py      # CSV-Import
│   ├── audit.py         # Audit-Log (read-only)
│   └── media.py         # Medien-Upload, IIIF-Manifest
├── services/            # Business-Logik (von Handlern aufgerufen)
│   ├── search_service.py    # ES-Indexierung, Reindex
│   ├── oaipmh_service.py    # OAI-XML-Serialisierung
│   ├── authority_service.py # Adapter-Registry
│   └── importer_service.py  # CSV-ETL
├── integrations/        # Externe Systeme
│   ├── elasticsearch.py     # ES-Client, Index-Settings, Mappings
│   ├── authority.py         # ABC AuthoritySource
│   ├── gnd_adapter.py       # lobid.org
│   ├── geonames_adapter.py  # GeoNames
│   ├── viaf_adapter.py
│   ├── wikidata_adapter.py
│   ├── tgn_adapter.py
│   └── iconclass_adapter.py
└── workers/
    └── index_tasks.py   # Celery-Tasks: reindex_all, index_single
```

## Datenmodell (Kern)

### Vier Primärtypen

Jeder Typ hat eine eigene Tabelle mit festen Spalten (`id`, `idno`, `status`, `created_at`, `updated_at`) und einem JSONB-Feld `metadata_` für alle frei konfigurierten Felder.

```
objects      (id, idno, status, metadata_ JSONB, ...)
entities     (id, entity_type, status, metadata_ JSONB, ...)
places       (id, place_type, lat, lon, geometry, status, metadata_ JSONB, ...)
occurrences  (id, occurrence_type, status, metadata_ JSONB, ...)
```

### Schema-Engine

```
field_definitions (id, target_type, name, label JSONB, field_type, is_required,
                   is_repeatable, sort_order, settings JSONB)
```

Definiert, welche Felder `metadata_` für jeden Typ enthält. Das Admin-UI liest diese Definitionen und rendert entsprechende Formularfelder.

### Relationen

```
relations (id, from_type, from_id, to_type, to_id, relation_type, metadata JSONB)
```

Generisch: alle vier Typen können beliebig miteinander verknüpft werden. `relation_type` zeigt auf ein Term im `relation_types`-Vokabular.

### Auth

```
users (id UUID, email, hashed_password, role, is_active, created_at)
```

Rollen: `admin` · `editor` · `cataloger` · `viewer`

## Auth-Flow

```
Browser/Client
    │  POST /v1/auth/token  {username, password}
    ▼
FastAPI auth.py
    │  bcrypt.verify()
    │  jose.jwt.encode({sub: user_id, role, exp})
    ▼
    ← {access_token, token_type: "bearer"}

Folgeaufrufe:
    Authorization: Bearer <token>
    ▼
dependencies.py: get_current_user()
    │  jwt.decode() → user_id
    │  DB lookup → User
    ▼
Handler bekommt CurrentUser-Objekt
```

Alle geschützten Endpoints verwenden `CurrentUser` als FastAPI-Dependency. Rollenprüfung über `require_role("admin")` oder `require_admin_or_editor()`.

## Frontend-Struktur

Zwei vollständig separate Vite/React-Apps:

### Admin (`frontend/admin/`)
```
src/
├── App.tsx                    # Einstieg, kein Router (hash-basiert)
├── api/client.ts              # Alle API-Calls, Token-Management
└── components/
    ├── layout/
    │   ├── AppShell.tsx       # Routing-State, Layout-Wrapper
    │   ├── Sidebar.tsx        # Linke Navigation
    │   └── Topbar.tsx         # Breadcrumb, Logout
    └── screens/               # Ein Screen = eine Ansicht
        ├── ScreenList.tsx     # Listenansicht (alle 4 Typen)
        ├── ScreenForm.tsx     # Formular (alle 4 Typen, dynamisch)
        ├── ScreenSchema.tsx   # Schema-Editor
        ├── ScreenVocab.tsx    # Vokabular-Editor
        ├── ScreenSettings.tsx # Portal-Konfiguration (Admin)
        ├── ScreenUsers.tsx    # Benutzerverwaltung
        ├── ScreenPages.tsx    # Statische Seiten
        ├── ScreenOAISets.tsx  # OAI-Sets-Verwaltung
        ├── ScreenImporter.tsx # CSV-Import
        └── ScreenAudit.tsx    # Audit-Log
```

Navigation ist **hash-basiert** (`#list`, `#schema`, `#settings` etc.) — kein React-Router.

### Portal (`frontend/portal/`)
```
src/
├── App.tsx          # HelmetProvider + BrowserRouter, Header, Footer, Routes
├── styles.css       # Alle Styles (CSS-Custom-Properties für Theming)
├── api/client.ts    # Alle API-Calls (kein Auth-Token)
├── hooks/
│   ├── useFieldLabels.ts   # Lädt Feld-Labels aus Schema
│   └── useBackToSearch.ts  # sessionStorage: Suche wiederherstellen
├── theme/
│   └── loader.ts    # CSS-Custom-Properties aus Portal-Config anwenden
└── pages/
    ├── HomePage.tsx
    ├── SearchPage.tsx         # Facettensuche (ES)
    ├── ObjectDetailPage.tsx
    ├── EntityDetailPage.tsx
    ├── PlaceDetailPage.tsx
    ├── OccurrenceDetailPage.tsx
    └── StaticPageView.tsx     # Markdown-Rendering
```

Navigation ist **URL-basiert** (React-Router v6, BrowserRouter).

## Elasticsearch-Index

Alle vier Typen landen in einem einzigen Index `katalon`. Das ES-Dokument flacht die wichtigsten Felder ab:

```json
{
  "_id": "<record-uuid>",
  "record_type": "object",
  "title": "...",
  "idno": "...",
  "status": "public",
  "metadata": { ... },           // JSONB-Kopie
  "related_entities": ["Name"],  // denormalisiert
  "related_places": ["Name"],
  "related_occurrences": ["Name"],
  "created_at": "...",
  "updated_at": "..."
}
```

Indexierung passiert synchron beim Speichern (`index_record()` in den API-Handlern) und asynchron per Celery-Task beim Massen-Reindex.

## Theming

Das Portal-Theme wird vollständig über CSS Custom Properties gesteuert. Die Werte kommen aus der `PortalConfig`-Tabelle und werden beim App-Start per `theme/loader.ts` auf `:root` angewendet. Admin-Einstellungen (Farben, Logo, Titel) schreiben in `portal_config`.

## Deployment

- **Entwicklung:** `docker compose -f docker-compose.yml -f docker-compose.dev.yml up`  
- **Produktion:** `docker compose -f docker-compose.yml -f docker-compose.prod.yml up`

Produktions-Besonderheiten: nginx übernimmt TLS-Terminierung, interne Services exponieren keine Ports nach außen (`ports: !reset []`), alle Secrets über `.env`.

→ Vollständige Produktionsdoku: [04_produktion.md](./04_produktion.md)
