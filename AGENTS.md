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
- `docs/` – Übergangskopie der technischen Dokumentation; primär gepflegt in `karkraeg/katalon-docs`
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
| Vier Primärtypen | Vier getrennte Tabellen für Bestandsdaten; Vorgänge als separater Procedure-Typ |

## Vier Bestands-Typen (alle mit frei konfigurierbaren Metadaten)

| Typ        | DB-Tabelle    | Beschreibung                         |
|------------|---------------|--------------------------------------|
| Object     | `objects`     | Artefakte: Fotos, Dokumente, Gemälde |
| Entity     | `entities`    | Personen, Organisationen             |
| Place      | `places`      | Geografische Orte (PostGIS)          |
| Occurrence | `occurrences` | Werke (FRBR), Ereignisse, Konzepte   |

**Alle vier Typen** haben dynamisch konfigurierbare Metadaten via `field_definitions`.

Vorgänge (Procedure) sind ein separater fünfter Typ für Leihverkehr, Erwerbung und Restaurierung.

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
| 5     | ✅      | Media & IIIF (Upload, Celery, Cantaloupe, Manifest) ← MVP-API  |
| 6     | ✅      | Admin-UI (React: Schema, CRUD, Medien) ← MVP komplett          |
| 7     | ✅      | Elasticsearch + Versionierung (Snapshots)                      |
| 8     | ✅      | Public-Portal (React: Suche, Facetten, IIIF-Viewer)            |
| 9     | ✅      | Authority-Plugin-System + Adapter GND/Geonames                 |
| 10    | ✅      | Smart Importer (Excel/CSV/XML ETL, Dry Run)                    |
| 11    | ✅      | OAI-PMH                                                        |
| 12    | ⚠️      | Hardening                                                      |
| 13    | ⚠️      | Inherited Fields (ES-Denormalisierung)                         |
| 14    | ✅      | Procedure-Typ (Leihverkehr, Erwerbung, Restaurierung)          |

## Nicht im Scope

- Video/Audio-Transcoding
- Eigenes Standortverwaltungsmodul
- Typ-Hierarchien (Post-MVP)
- Sets (Nice-to-have, Post-MVP)

## User-Profil

Karl kennt sich gut mit Python und React aus. Keine grundlegenden Erklärungen zu diesen Technologien nötig. Er kennt CollectiveAccess-Konzepte (dynamische Schemata, Vokabulare, Entitätsrelationen).

## Debugging

- Wenn ich Fehler berichte, schau immer in die Logs der entsprechenden Container statt Annahmen zu treffen.

## Python/uv Hinweise

- Backend-Python-Kommandos immer aus `backend/` ausführen. Im Repo-Root existiert auch eine `.venv`; von dort gestartete Backend-Tests können im falschen Interpreter landen und dann Dependencies wie `jinja2` "verlieren".
- Backend-Tests immer mit einem mindestens 32 Zeichen langen Testschlüssel starten, z. B. `KATALON_SECRETS_KEY="test-katalon-secrets-key-32-chars" uv run pytest ...`. Nicht erst einen Lauf ohne diese Variable versuchen.
- Wenn `uv` über `backend/uv.lock` stolpert: der problematische Fall ist `click-didyoumean` mit inkonsistentem Lock-Eintrag (`version = "0.3.2"` zeigt auf `click_didyoumean-0.3.1` Dateien). Bis Upstream sauber ist, `click-didyoumean==0.3.1` beibehalten.

## Port-Regel Dev vs. Prod-Compose

**Port-Verwechslung vermeiden:**

- `http://localhost/admin/` = Admin im normalen/production-like Compose-Stack (über äußeres `nginx`, Port 80)
- `http://localhost/` = Portal im normalen/production-like Compose-Stack (über äußeres `nginx`, Port 80)
- `http://localhost:3000` / `http://localhost:3001` = Admin/Portal-Container **direkt**, nur zum Debuggen des jeweiligen Containers geeignet. **Nicht zum normalen Testen verwenden** – der Admin-Container wird mit `VITE_BASE_PATH=/admin/` gebaut (siehe unten), Assets liegen also unter `/admin/assets/...`. Direkter Aufruf von `localhost:3000/` liefert nur die HTML-Shell, die JS/CSS-Requests laufen ins SPA-Fallback (`text/html` statt `application/javascript`) → weiße Seite.
- `http://localhost:4000` = Admin **nur** im Dev-Compose-Stack (`docker-compose.dev.yml`)
- `http://localhost:4001` = Portal **nur** im Dev-Compose-Stack (`docker-compose.dev.yml`)

**Wichtig:** Wenn nicht explizit gesagt wird, dass der Dev-Stack gemeint ist, verwende für Browser-Checks standardmäßig `http://localhost/admin/` und `http://localhost/`, nicht die direkten Container-Ports.

## Kritische Build-Konfigurationen – NICHT ÄNDERN ohne Test

Die folgenden Konfigurationswerte sind deployment-kritisch. Änderungen ohne Verifikation der Produktionsumgebung brechen die App still (kein Build-Fehler, aber falsche Laufzeit-Pfade):

| Datei | Wert | Warum kritisch |
|-------|------|---------------|
| `docker/Dockerfile.admin` | `VITE_BASE_PATH=/admin/` | Ohne diesen Wert baut Vite Assets mit absolutem Pfad `/assets/`, der vom äußeren nginx zum Portal geroutet wird statt zum Admin-Container. Die Admin-UI lädt dann nicht (404 für JS/CSS). |

**Regel:** Vor jeder Änderung an `docker/Dockerfile.admin`, `docker/nginx.admin.conf` oder `frontend/admin/vite.config.ts` explizit prüfen ob `VITE_BASE_PATH` und nginx-`location`-Blöcke konsistent sind. Nach dem Deploy `https://katalon.kraegelin.dev/admin/` im Browser öffnen und JS/CSS-Requests in den DevTools prüfen.

## Datensicherheit – ABSOLUTE VERBOTE

**NIEMALS die Datenbank-Volumes löschen, neu erstellen oder `docker compose down -v` ausführen ohne explizite Bestätigung von Karl.** Das gilt auch dann, wenn es als schnelle Lösung erscheint (z. B. bei Passwort-Konflikten, Schema-Problemen oder Container-Fehlern). Datenverlust ist irreversibel.

Stattdessen bei DB-Problemen:
1. Logs lesen, Root Cause verstehen
2. Karl informieren und Optionen vorlegen
3. Erst nach ausdrücklicher Freigabe handeln

## Code Navigation

A CodeGraph MCP server is available with a pre-indexed knowledge graph of this codebase.
Prefer these tools over grep/find for code exploration:

- `codegraph_context` — get structured context for a task (use this first)
- `codegraph_search` — find symbols by name
- `codegraph_callers` / `codegraph_callees` — trace call relationships
- `codegraph_impact` — blast radius before changing something

Always use CodeGraph before falling back to grep or sequential file reads.

## Dev Knowledge Base (OKF)

`.agents/knowledge/` ist eine dev-only [OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)-Wissensbasis für Katalon selbst — architektonische Entscheidungen mit Begründung, nicht Code-Doku. Getrennt von `.agents/DEV.md`/`IMPLEMENTIERUNGSPLAN.md`/`PLAN*.md` (die bleiben lebende Prozessdokumente).

**Nachschlagen**: Bei Architektur-/Design-Fragen ("warum ist das so gebaut?") erst `.agents/knowledge/decisions/index.md` prüfen, bevor Code-Archäologie betrieben wird. Lokale HTML-Ansicht: `make knowledge-site`.

**Pflege**: Nach jeder Session, in der eine architektonisch relevante Entscheidung getroffen wird (neue Komponente, Trade-off zwischen Ansätzen, Abweichung von einem bestehenden Muster) — nicht bei reinen Bugfixes oder Feature-Implementierungen ohne Designfrage — ein neues Konzept unter `.agents/knowledge/decisions/` anlegen (Format wie bestehende Dateien: YAML-Frontmatter mit `type: Decision`, Sections Kontext/Entscheidung/Begründung/Citations) und in `decisions/index.md` verlinken.

## CodeAlmanac

Vor jeder Umsetzung die relevanten CodeAlmanac-Seiten konsultieren und den Plan auf Widersprüche prüfen. Zusätzlich mögliche UX-Einwände gegen `PRODUCT.md` und `DESIGN.md` prüfen und vor der Umsetzung benennen; auch technisch getriebene Features auf Auswirkungen für Bedienung, Accessibility, Fehlerzustände und Responsive-Verhalten prüfen.

Nach Implementierungen, die dokumentiertes Verhalten, Abläufe oder Architektur ändern, `almanac/` aktualisieren und die betroffenen Seiten gegen den tatsächlichen Code verifizieren. Veraltete Seiten korrigieren oder kennzeichnen; rein aus dem Code ablesbare Details nicht duplizieren.

## Kontext-Dateien — Lazy Loading

Lebende Prozess-/Produkt-Dokumente bleiben an ihrem Ort (nicht Teil von `.agents/knowledge/`, siehe oben), werden aber nur bei Bedarf gelesen statt pauschal vorausgesetzt:

- Frage zu Roadmap, Phasenstatus, offenen Issues, Priorität → `.agents/IMPLEMENTIERUNGSPLAN.md`
- Frage zu lokalem Setup, Dev-Workflow, Docker-Stack-Wahl → `.agents/DEV.md`
- Frage zum Datenmodell im Detail (über die Kurzfassung hier hinaus) → `KONZEPT.md`
- UI-/UX-/Produktentscheidung, Zielgruppe, Design-Prinzipien → `PRODUCT.md` + `DESIGN.md`

## Coding Rules — Lazy Loading

Sprachspezifische Coding-Regeln liegen nicht hier, sondern in `.agents/rules/`, und werden nur bei Bedarf geladen:

- Wird `backend/` angefasst → vorher `.agents/rules/backend.md` lesen.
- Wird `frontend/admin/` oder `frontend/portal/` angefasst → vorher `.agents/rules/frontend.md` lesen.
- Beide betroffen (siehe Full-Stack Exploration Rule unten) → beide Dateien lesen.

## Full-Stack Exploration Rule

**Any feature touches both backend AND frontend.** Before starting exploration or planning:

1. Read backend model/schema first
2. Immediately also read the corresponding frontend component(s) — search `frontend/admin/src` and `frontend/portal/src`
3. Never conclude "what exists" from backend alone

Key mappings:
- Schema fields → `frontend/admin/src/screens/ScreenSchema.tsx`
- Record forms → `frontend/admin/src/screens/ScreenForm.tsx`
- Vocabularies → `frontend/admin/src/screens/ScreenVocab.tsx`
- Relations panel → `frontend/admin/src/screens/ScreenForm.tsx` (Beziehungen section)
- Public record view → `frontend/portal/src/`

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

Siehe `.agents/IMPLEMENTIERUNGSPLAN.md` und die GitHub Roadmap für aktuelle Prioritäten.
