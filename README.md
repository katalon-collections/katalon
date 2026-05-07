# Katalon

Open-Source Metadata Management System (MMS) für den GLAM-Sektor (Galerien, Bibliotheken, Archive, Museen). Moderner Python/React-Rewrite der Kernfunktionalitäten von CollectiveAccess.

## Status

| Meilenstein                                 | Status                                        |
|---------------------------------------------|-----------------------------------------------|
| Phase 0 – Docker-Infrastruktur              | ✅ Fertig                                      |
| Phase 1 – Core-Datenbank (ORM + Alembic)    | ✅ Fertig                                      |
| Phase 2 – Schema-Engine                     | ✅ Fertig                                      |
| Phase 3 – CRUD alle 4 Typen + Relationen    | ✅ Fertig                                      |
| Phase 4 – Auth (JWT) + Audit Log            | ✅ Fertig                                      |
| Phase 5 – Media & IIIF                      | ✅ Grundgerüst fertig (Upload, Celery, IIIF)  |
| Phase 6 – Admin-UI (React/TypeScript)       | ✅ Fertig — alle Screens implementiert         |
| Phase 7 – Elasticsearch + Versionierung     | ✅ Fertig                                      |
| Phase 8 – Public-Portal + Theme-System      | ✅ Fertig                                      |
| Phase 9 – Authority-Adapter (GND, Geonames) | ✅ Fertig                                      |
| Phase 10 – Smart Importer                   | ✅ Fertig                                      |
| Phase 11 – OAI-PMH                          | ✅ Fertig                                      |
| Phase 12 – Hardening                        | ✅ Fertig                                      |

## Schnellstart (Entwicklung)

```bash
# Alle Services starten (DB, Redis, ES, Cantaloupe, API, Worker, Frontend)
docker compose up

# Admin-UI (Dev): http://localhost:4000
# Portal (Dev):   http://localhost:4001
# API + Docs:     http://localhost:8000/docs
```

### Voraussetzungen

- Docker + Docker Compose v2
- (Optional für lokale Entwicklung ohne Docker) Python 3.12+, Node 20+

### Backend lokal

```bash
cd backend
uv pip install -e ".[dev]"

# Datenbank-Migrationen
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
│   └── portal/               # React + TypeScript (Vite) — Public-Portal
└── docker/                   # Dockerfiles + nginx
```

**Stack:** FastAPI · PostgreSQL 16 + PostGIS · Elasticsearch 8 · Redis · Celery · Cantaloupe (IIIF) · React 18 + TypeScript

## API

OpenAPI-Dokumentation: `http://localhost:8000/docs`

Wichtige Endpunkte:

| Methode        | Pfad                              | Beschreibung                           |
|----------------|-----------------------------------|----------------------------------------|
| POST           | `/v1/auth/token`                  | JWT-Login                              |
| GET            | `/v1/objects`                     | Objekte auflisten (Pagination, Filter) |
| POST           | `/v1/objects`                     | Neues Objekt anlegen                   |
| GET/PUT/DELETE | `/v1/objects/{id}`                | Objekt lesen/aktualisieren/löschen     |
| GET            | `/v1/schema/{target_type}`        | Felddefinitionen abrufen               |
| GET/POST       | `/v1/schema/import`               | Schema aus YAML/JSON importieren       |
| GET            | `/v1/vocabularies`                | Vokabulare auflisten                   |
| POST           | `/v1/vocabularies/{id}/import`    | Vokabular-Terme aus CSV/JSON importieren (Dry-Run/Replace) |
| GET            | `/v1/search`                      | Volltext- und Facettensuche            |
| POST           | `/v1/pids/urn/register`           | URN via DNB-API registrieren (PID-Feld) |
| GET            | `/v1/portal/config`               | Portal-Konfiguration                   |
| POST           | `/v1/portal/logo`                 | Logo hochladen                         |
| GET            | `/v1/audit`                       | Audit-Log abrufen                      |

### DNB-URN (PID)

- URN-Vergabe ist per Umgebungsvariablen konfigurierbar (`DNB_URN_*` in `.env.example`).
- Für lokale Entwicklung kann der Mock-Endpunkt genutzt werden: `DNB_URN_API_URL=http://localhost:8000/v1/dnb-urn-mock`.

### Vokabular-Import (CSV/JSON)

Endpoint: `POST /v1/vocabularies/{vocab_id}/import?dry_run=true|false&strategy=append|replace`  
Request: `multipart/form-data` mit `file` und optional `mapping` (nur CSV/TSV).

#### Welche Felder sind nötig?

- **Kein `id` erforderlich** (IDs werden intern erzeugt).
- **Kein `title` erforderlich**.
- Pflicht ist nur der **Term-Schlüssel** (`term`), also der interne Begriff.
- Optional:
  - `label:<sprache>` (z. B. `label:de`, `label:en`) für Anzeigenamen/Übersetzungen
  - `parent_term` für Hierarchie
  - `external_id` als externe Kennung im Importdatensatz

#### CSV/TSV

CSV braucht ein Mapping-Feld (`mapping` als JSON), z. B.:

```json
{
  "begriff": "term",
  "anzeige_de": "label:de",
  "anzeige_en": "label:en",
  "oberbegriff": "parent_term",
  "gnd_id": "external_id"
}
```

Beispiel-CSV:

```csv
begriff;anzeige_de;anzeige_en;oberbegriff;gnd_id
kunst;Kunst;Art;;
malerei;Malerei;Painting;kunst;4065684-4
```

#### JSON (auch hierarchisch)

Unterstützt flache Listen oder verschachtelte `children`:

```json
[
  {
    "term": "kunst",
    "label": {"de": "Kunst", "en": "Art"},
    "children": [
      {"term": "malerei", "label": {"de": "Malerei", "en": "Painting"}}
    ]
  }
]
```

#### Dry-Run und Strategie

- `dry_run=true`: prüft Datei, schreibt nichts in die DB (Vorschau + Fehlerliste).
- `strategy=append`: vorhandene Terme bleiben, gleiche `term`-Werte werden aktualisiert.
- `strategy=replace`: vorhandene Terme des Vokabulars werden ersetzt.

## Admin-UI

IBM Plex Sans + IBM Plex Mono · Dark Navy Sidebar · Screens:

- **Objekte / Entitäten / Orte / Occurrences** — Tabellenansicht + Erfassungsformular
- **Schemata** — Feldkonfiguration pro Typ, YAML/JSON-Import
- **Vokabular** — Kontrollierte Listen verwalten
- **Statische Seiten** — Portal-Inhaltsseiten
- **Importer** — CSV/Excel-Import-Wizard
- **Audit-Log** — Änderungshistorie
- **Benutzer** — Benutzerverwaltung (nur Admin)
- **Einstellungen** — Portal-Konfiguration, Logo-Upload, Farben (nur Admin)

## Offene Punkte

Tracked als GitHub Issues: https://github.com/karkraeg/Katalon/issues

Aktuell priorisiert:

- [#83](https://github.com/karkraeg/Katalon/issues/83) **Relation-Facetten im Portal** — beim Objekt-Browsing nach verknüpften Entitäten/Orten/Occurrences filtern
- [#78](https://github.com/karkraeg/Katalon/issues/78) Relation-Type-Labels aus Vokabular auflösen
- [#77](https://github.com/karkraeg/Katalon/issues/77) „Zurück zur Suche" auf Detailseiten
- [#75](https://github.com/karkraeg/Katalon/issues/75) IIIF-Manifest-Link auf ObjectDetailPage

## Theme-System

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
