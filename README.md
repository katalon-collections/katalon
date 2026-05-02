# Katalon

Open-Source Metadata Management System (MMS) für den GLAM-Sektor (Galerien, Bibliotheken, Archive, Museen). Moderner Python/React-Rewrite der Kernfunktionalitäten von CollectiveAccess.

## Status

| Meilenstein                                 | Status                                         |
|---------------------------------------------|------------------------------------------------|
| Phase 0 – Docker-Infrastruktur              | ✅ Fertig                                       |
| Phase 1 – Core-Datenbank (ORM + Alembic)    | ✅ Fertig                                       |
| Phase 2 – Schema-Engine                     | ✅ Fertig                                       |
| Phase 3 – CRUD alle 4 Typen + Relationen    | ✅ Fertig (Objekte vollständig, weitere folgen) |
| Phase 4 – Auth (JWT) + Audit Log            | ✅ Fertig                                       |
| Phase 5 – Media & IIIF                      | 🔄 Grundgerüst vorhanden                       |
| Phase 6 – Admin-UI (React/TypeScript)       | ✅ Fertig — alle 6 Screens implementiert        |
| Phase 7 – Elasticsearch + Versionierung     | ✅ Fertig                                       |
| Phase 8 – Public-Portal + Theme-System      | ✅ Fertig                                       |
| Phase 9 – Authority-Adapter (GND, Geonames) | ✅ Fertig                                       |
| Phase 10 – Smart Importer                   | ✅ Fertig                                       |
| Phase 11 – OAI-PMH                          | ✅ Fertig                                       |
| Phase 12 – Hardening                        | ✅ Fertig                                       |

## Schnellstart (Entwicklung)

```bash
# Alle Services starten (DB, Redis, ES, Cantaloupe, API, Worker, Admin-Frontend)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# Admin-UI: http://localhost:3000
# API + Docs: http://localhost:8000/api/docs
```

### Voraussetzungen

- Docker + Docker Compose v2
- (Optional für lokale Entwicklung ohne Docker) Python 3.12+, Node 20+

### Backend lokal

```bash
cd backend
pip install uv
uv pip install -e ".[dev]"

# Datenbank-Migration
alembic -c migrations/alembic.ini upgrade head

# API starten
uvicorn katalon.main:app --reload
```

### Demo-Daten einspielen (ICS-Beispieldatensatz)

Legt Felddefinitionen, Vokabulare und Beispieldatensätze nach dem Datenmodell der Internationalen Computerspielesammlung an (Computerspiele als Objekte, Werke/Werkversionen als Occurrences, Entitäten und Orte vollständig verknüpft):

```bash
# API muss laufen (docker compose up)
uv run --project backend python backend/scripts/seed_ics_demo.py

# Andere Instanz oder andere Zugangsdaten:
uv run --project backend python backend/scripts/seed_ics_demo.py \
  --base-url http://localhost:8000 \
  --email admin@katalon.dev \
  --password admin
```

### Admin-Frontend lokal

```bash
cd frontend/admin
npm install
npm run dev        # http://localhost:5173
```

Umgebungsvariable für lokale API: `VITE_API_URL=http://localhost:8000`

## Architektur

```text
katalon/
├── backend/                  # Python 3.12 / FastAPI
│   ├── src/katalon/
│   │   ├── api/v1/           # REST-Endpoints
│   │   ├── core/             # ORM-Models, Pydantic-Schemas, Auth
│   │   ├── services/         # Business-Logik
│   │   ├── workers/          # Celery-Tasks
│   │   └── integrations/     # Cantaloupe (IIIF), Elasticsearch
│   └── migrations/           # Alembic
├── frontend/
│   ├── admin/                # React + TypeScript (Vite) — Eingabeoberfläche
│   └── portal/               # Public-Portal (noch ausstehend)
└── docker/                   # Dockerfiles + nginx
```

**Stack:** FastAPI · PostgreSQL 16 + PostGIS · Elasticsearch 8 · Redis · Celery · Cantaloupe (IIIF) · React 18 + TypeScript

## API

OpenAPI-Dokumentation: `http://localhost:8000/api/docs`

Wichtige Endpunkte:

| Methode        | Pfad                       | Beschreibung                           |
|----------------|----------------------------|----------------------------------------|
| POST           | `/v1/auth/token`           | JWT-Login                              |
| GET            | `/v1/objects`              | Objekte auflisten (Pagination, Filter) |
| POST           | `/v1/objects`              | Neues Objekt anlegen                   |
| GET/PUT/DELETE | `/v1/objects/{id}`         | Objekt lesen/aktualisieren/löschen     |
| GET            | `/v1/schema/{target_type}` | Felddefinitionen abrufen               |
| GET            | `/v1/vocabularies`         | Vokabulare auflisten                   |
| GET            | `/v1/audit`                | Audit-Log abrufen                      |

## Admin-UI Design

IBM Plex Sans + IBM Plex Mono · Dark Navy Sidebar · 6 Screens:

- **Objekte** — Tabellenansicht + Erfassungsformular
- **Schemata** — Feldkonfiguration pro Typ
- **Vokabular** — Kontrollierte Listen verwalten
- **Importer** — CSV/Excel-Import-Wizard
- **Audit-Log** — Änderungshistorie

**Screens ohne Design (Post-MVP):** Entitäten, Orte, Occurrences, Benutzer, Einstellungen

## Offene Punkte für Agents

Diese Liste ist die aktuelle Arbeitsübersicht für die nächsten Implementierungsschritte. Die Reihenfolge ist bewusst pragmatisch: erst die Kern-Workflows, dann die Präsentation.

### Priorität 1: Admin-Workflows fertig machen

- **Schemata**: Neues Feld anlegen, bestehendes Feld bearbeiten, löschen und sortieren persistieren; aktuell ist der Screen noch stark mock-basiert.
- **Objekte**: Objekt bearbeiten und speichern gegen die echte API verdrahten; Listenansicht, Filter und Statuswechsel brauchen echte CRUD-Integration.
- **Vokabular**: Neuen Term anlegen, bearbeiten, löschen und hierarchische Beziehungen speichern; aktuell ist der Screen ebenfalls noch Demo-Logik.
- **Bilderupload**: Upload-Endpunkt, Dateiablage und IIIF/Manifest-Verknüpfung im Admin-UI-End-to-End fertigstellen.
- **Suche im Admin-Panel**: Globale Suche im Topbar-/Sidebar-Kontext an die API anbinden, nicht nur lokal filtern.

### Priorität 2: Präsentationsoberfläche sichtbar machen

- **Public-Portal auf Demo-Niveau bringen**: Startseite, Suche und Detailansicht so abrunden, dass man die Sammlung überzeugend präsentieren kann.
- **IIIF-/Viewer-Erlebnis**: Objekt-Detail mit echten Medien und Manifesten verbinden, damit das Portal nicht nur wie ein Platzhalter wirkt.
- **Theme-Story demonstrieren**: Ein sichtbares Beispiel-Theme oder ein klarer Theme-Wechsel im Portal wäre für Demos sehr hilfreich.

### Priorität 3: Plattform abrunden

- **Admin- und Portal-Routen sauber mit API verbinden**: Keine Mock-Daten mehr dort, wo echte Daten verfügbar sind.
- **Fehlerzustände und Ladezustände**: In den wichtigsten Screens sauber ausbauen, damit die App robust wirkt.
- **CRUD für weitere Typen**: Entitäten, Orte und Occurrences im Admin-UI nachziehen.

### Gute Agenten-Reihenfolge

1. Schema-Editor und Vokabulare gegen echte API verdrahten.
2. Objekt-CRUD und Medienupload fertigstellen.
3. Globale Suche im Admin-Panel anbinden.
4. Public-Portal optisch und funktional präsentationsreif machen.
5. Danach Entitäten, Orte und Occurrences im Admin ergänzen.

## Theme-System (Post-MVP)

Das Discovery-Portal ist vollständig themebar per **Drop-in Bundle** — kein Rebuild, kein Store.

```bash
# 1. Theme ablegen
cp -r mein-archiv/ /var/lib/katalon/themes/mein-archiv/

# 2. Aktivieren
echo "PORTAL_THEME=mein-archiv" >> .env
docker compose restart portal
```

Ein Theme-Bundle besteht aus `theme.json` (CSS-Tokens, Fonts, Logo) + optionalem `custom.css`.  
Das Admin-UI ist bewusst nicht themebar. Details → `KONZEPT.md` Abschnitt 11.
