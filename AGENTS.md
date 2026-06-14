# Katalon – Projektkontext für Claude

## Was ist dieses Projekt?

Katalon ist ein Open-Source Metadata Management System (MMS) für den GLAM-Sektor (Galleries, Libraries, Archives, Museums). Es ist ein moderner Python/React-Rewrite der Kernfunktionalitäten von **CollectiveAccess** (PHP-Monolith mit XML-Konfiguration).

**Kernproblem von CollectiveAccess, das gelöst wird:**

- Monolithisches PHP, schwer wartbar
- XML-Konfiguration mit hoher Einstiegshürde
- Keine saubere API für moderne Frontends
- Keine Python/Datenscience-Integration

## Dateien in diesem Verzeichnis

- `KONZEPT.md` – vollständiges Konzeptdokument mit Datenmodell
- `.agents/IMPLEMENTIERUNGSPLAN.md` – detaillierter Phasenplan
- `.agents/DEV.md` – Entwickler-Setup und Workflows
- `docs/` – technische Dokumentation (Architektur, Datenmodell, OAI, Produktion, Upgrading …)
- `e2e/` – Playwright-E2E-Tests

## Fixierte Architekturentscheidungen

| Entscheidung     | Festgelegt                                                 |
|------------------|------------------------------------------------------------|
| Name             | **Katalon** (kein PyAccess – verwerfen)                    |
| Backend          | Python 3.12+ / FastAPI                                     |
| Datenbank        | PostgreSQL 16 + PostGIS + JSONB                            |
| Suche            | Elasticsearch 8.x                                          |
| Bildserver       | Cantaloupe (IIIF Image API 3)                              |
| Task Queue       | Celery + Redis                                             |
| Frontend         | React + TypeScript (Vite) – zwei separate Apps             |
| Deployment       | Docker Compose                                             |
| IIIF im MVP      | Ja                                                         |
| Vier Primärtypen | Vier getrennte Tabellen (nicht generische records-Tabelle) |

## Vier Primärtypen (alle mit frei konfigurierbaren Metadaten)

| Typ        | DB-Tabelle    | Beschreibung                         |
|------------|---------------|--------------------------------------|
| Object     | `objects`     | Artefakte: Fotos, Dokumente, Gemälde |
| Entity     | `entities`    | Personen, Organisationen             |
| Place      | `places`      | Geografische Orte (PostGIS)          |
| Occurrence | `occurrences` | Werke (FRBR), Ereignisse, Konzepte   |

**Alle vier Typen** haben dynamisch konfigurierbare Metadaten via `field_definitions`.

## Monorepo-Struktur

```text
katalon/
├── backend/
│   ├── src/katalon/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── core/          # ORM models, Pydantic schemas, dependencies
│   │   ├── api/v1/        # Alle Endpoints
│   │   ├── services/      # Business-Logik
│   │   ├── workers/       # Celery tasks
│   │   ├── integrations/  # ES, Cantaloupe, Authority-Adapter
│   │   └── management/    # CLI-Verwaltungsbefehle
│   ├── tests/
│   ├── migrations/        # Alembic
│   └── pyproject.toml
├── frontend/
│   ├── admin/             # Eingabeoberfläche (auth-geschützt)
│   └── portal/            # Public-Portal (Suche, IIIF)
├── docker/
├── docs/                  # Technische Dokumentation
├── e2e/                   # Playwright-E2E-Tests
├── docker-compose.yml
└── CLAUDE.md              # diese Datei
```

## Schlüsselentscheidungen Datenmodell

### Schema-Engine (gilt für alle 4 Typen)

```sql
field_definitions (
    id UUID, target_type VARCHAR,  -- object/entity/place/occurrence
    name VARCHAR, label JSONB,     -- {"de": "...", "en": "..."}
    field_type VARCHAR,            -- text/date/number/geo/vocab/relation/boolean
    is_required BOOLEAN, is_repeatable BOOLEAN,
    sort_order INT, settings JSONB
)
```

### Wiederholbare Felder (JSONB-Arrays)

```json
{
  "title": [{"value": "Straße in Marrakesch", "lang": "de"}],
  "photographer": [{"entity_id": "uuid-1", "role": "Auftraggeber"}]
}
```

### Relationen (generisch, mit Metadaten auf der Relation)

```sql
relations (
    id UUID, from_type VARCHAR, from_id UUID,
    to_type VARCHAR, to_id UUID,
    relation_type VARCHAR, metadata JSONB
)
```

Alle 4 Typen können beliebig miteinander verknüpft werden.

### Audit Log (Pflicht)

```sql
audit_log (record_type, record_id, user_id, action, changed_fields JSONB, created_at)
```

### Versionierung (Snapshots)

```sql
record_snapshots (record_type, record_id, label, snapshot JSONB, created_by, created_at)
```

### Authority-Plugin-System

Abstrakte Python-Klasse `AuthoritySource(ABC)` mit `search()` und `fetch()`.
Adapter werden in DB registriert. Erste Adapter: GND, Geonames.

```sql
authority_sources (id VARCHAR, label, adapter_class, config JSONB, is_enabled)
```

## Phasenplan (MVP = Phasen 0–6)

| Phase | Status | Meilenstein                                                    |
|-------|--------|----------------------------------------------------------------|
| 0–1   | ✅      | Infra (Docker Compose, alle Services) + Core-DB (ORM, Alembic) |
| 2     | ✅      | Schema-Engine (field_definitions, repeatable, Vokabulare)      |
| 3     | ✅      | CRUD alle 4 Typen + generische Relationen mit Metadaten        |
| 4     | ✅      | Auth (FastAPI-Users, JWT, Rollen) + Audit Log                  |
| 5     | ⚠️      | Media & IIIF (Upload, Celery, Cantaloupe, Manifest) ← MVP-API  |
| 6     | ✅      | Admin-UI (React: Schema, CRUD, Medien) ← MVP komplett          |
| 7     | ⚠️      | Elasticsearch + Versionierung (Snapshots)                      |
| 8     | ✅      | Public-Portal (React: Suche, Facetten, IIIF-Viewer)            |
| 9     | ✅      | Authority-Plugin-System + Adapter GND/Geonames                 |
| 10    | ⚠️      | Smart Importer (Excel/CSV ETL, Dry Run)                        |
| 11    | ⚠️      | OAI-PMH                                                        |
| 12    | 🔲     | Hardening                                                      |

## Nicht im Scope

- Video/Audio-Transcoding
- Leihverkehr / Standortverwaltung
- Typ-Hierarchien (Post-MVP)
- Sets (Nice-to-have, Post-MVP)

## User-Profil

Karl kennt sich gut mit Python und React aus. Keine grundlegenden Erklärungen zu diesen Technologien nötig. Er kennt CollectiveAccess-Konzepte (dynamische Schemata, Vokabulare, Entitätsrelationen).

## Debugging

- Wenn ich Fehler berichte, schau immer in die Logs der entsorechenden Container statt Annahmen zu treffen.

## Code Navigation

A CodeGraph MCP server is available with a pre-indexed knowledge graph of this codebase.
Prefer these tools over grep/find for code exploration:

- `codegraph_context` — get structured context for a task (use this first)
- `codegraph_search` — find symbols by name
- `codegraph_callers` / `codegraph_callees` — trace call relationships
- `codegraph_impact` — blast radius before changing something

Always use CodeGraph before falling back to grep or sequential file reads.

## Versionierung

Katalon verwendet Semantic Versioning (`MAJOR.MINOR.PATCH`).

**Regel: Mit jedem Commit die Patch-Version hochziehen** (`0.1.0` → `0.1.1` → `0.1.2` …).

Dazu bei jedem Commit:
1. `backend/pyproject.toml` — `version = "x.y.z"`
2. `frontend/admin/package.json` — `"version": "x.y.z"`
3. `frontend/portal/package.json` — `"version": "x.y.z"`
4. `CHANGELOG.md` — neuen Eintrag unter `[Unreleased]` oder neuen `[x.y.z]`-Block
5. Nach dem Commit: `git tag vx.y.z && git push origin vx.y.z`

**Minor-Bump** (`0.1.x` → `0.2.0`): neue Features oder abgeschlossene Phase → kurz informieren, Karl entscheidet.
**Major-Bump** (`0.x.y` → `1.0.0`): erster öffentlicher Release → explizite Absprache.

## Nächster logischer Schritt

Siehe `.agents/IMPLEMENTIERUNGSPLAN.md` für aktuelle Prioritäten.
