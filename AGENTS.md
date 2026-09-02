# Katalon – Projektkontext für Claude

## Was ist dieses Projekt?

Katalon ist ein Open-Source Metadata Management System (MMS) für den GLAM-Sektor (Galleries, Libraries, Archives, Museums), gebaut mit Python/FastAPI-Backend und React-Frontends.

**Lizenz:** AGPL-3.0-or-later (`LICENSE`). Jede Code-Datei (Backend `.py`, Frontend `.ts`/`.tsx`, E2E-Tests) trägt einen SPDX-Header (`SPDX-License-Identifier: AGPL-3.0-or-later` + `Copyright (c) 2026 Karl Krägelin`) — neue Dateien bekommen denselben Header. Details/Begründung: `almanac/decisions/operations/license-and-branding.md`.

**Name:** Extern (Browser-Titel, Login-Screen, README, "Über Katalon"-Seite in der Admin-UI) heißt die Software **"Katalon Collections"** — Abgrenzung zum unabhängigen Produkt katalon.com. Intern (Code, Packages, Repo-Name, Admin-Sidebar/Breadcrumbs, alle Doku-Dateien in diesem Repo) bleibt es kurz **"Katalon"**. Keine Code-Identifier umbenennen.

**Design-Ziele:**

- Schema-Konfiguration über die Oberfläche statt über Konfigurationsdateien
- Saubere REST-API für moderne Frontends und Integrationen
- Native Python/Datenscience-Integration

## Dateien in diesem Verzeichnis

- `KONZEPT.md` – vollständiges Konzeptdokument mit Datenmodell
- GitHub-Roadmap (#260–#267) – Phasenstatus und Prioritäten (ersetzt IMPLEMENTIERUNGSPLAN.md)
- `.agents/DEV.md` – Entwickler-Setup und Workflows
- `docs/` – technische Entwickler- und Betriebsdokumentation
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

## Nicht im Scope

- Video/Audio-Transcoding
- Eigenes Standortverwaltungsmodul
- Typ-Hierarchien (Post-MVP)
- Sets (Nice-to-have, Post-MVP)

## Debugging

- Wenn ich Fehler berichte, schau immer in die Logs der entsprechenden Container statt Annahmen zu treffen.

## Python/uv Hinweise

- Backend-Python-Kommandos nach Möglichkeit aus `backend/` ausführen. Das Repo-Root ist seit dem uv-Workspace (`pyproject.toml` mit `[tool.uv.workspace] members = ["backend"]`) für `uv run` aus dem Root nutzbar (z. B. `uv run katalon-manage`), `backend/.venv/bin/katalon-manage` (expliziter Interpreter) funktioniert ebenfalls. `Settings` liest `.env` seit der Source-Relokalisierung aus `backend/.env` bzw. Repo-Root (siehe `almanac/reference/operations/environment-and-secrets.md`).
- Backend-Tests immer mit einem mindestens 32 Zeichen langen Testschlüssel starten, z. B. `KATALON_SECRETS_KEY="test-katalon-secrets-key-32-chars" uv run pytest ...`. Nicht erst einen Lauf ohne diese Variable versuchen. Via Root-`.env` kann die Variable implizit gesetzt sein, da `Settings` die `.env` source-relativ auflöst.
- Wenn `uv` über den Workspace-Lock stolpert: der problematische Fall ist `click-didyoumean` mit inkonsistentem Lock-Eintrag (`version = "0.3.2"` zeigt auf `click_didyoumean-0.3.1` Dateien). Effektiver Lock ist seit dem uv-Workspace das Root-`uv.lock` (nicht mehr `backend/uv.lock`). Bis Upstream sauber ist, `click-didyoumean==0.3.1` beibehalten.

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

`.agents/knowledge/` ist eine dev-only [OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)-Wissensbasis für Katalon selbst — architektonische Entscheidungen mit Begründung, nicht Code-Doku. Getrennt von `.agents/DEV.md`/`PLAN*.md` (die bleiben lebende Prozessdokumente).

**Nachschlagen**: Bei Architektur-/Design-Fragen ("warum ist das so gebaut?") erst `.agents/knowledge/decisions/index.md` prüfen, bevor Code-Archäologie betrieben wird. Lokale HTML-Ansicht: `make knowledge-site`.

**Pflege**: Nach jeder Session, in der eine architektonisch relevante Entscheidung getroffen wird (neue Komponente, Trade-off zwischen Ansätzen, Abweichung von einem bestehenden Muster) — nicht bei reinen Bugfixes oder Feature-Implementierungen ohne Designfrage — ein neues Konzept unter `.agents/knowledge/decisions/` anlegen (Format wie bestehende Dateien: YAML-Frontmatter mit `type: Decision`, Sections Kontext/Entscheidung/Begründung/Citations) und in `decisions/index.md` verlinken.

## Anwender-Doku — Pflege

Die Anwenderdokumentation liegt in `katalon-collections/katalon-docs` und wird unter `https://katalon-collections.github.io/katalon-docs/` veröffentlicht. Die Admin-UI verlinkt ihre Hilfeziele direkt auf diese Seiten. `docs/` in diesem Repository enthält nur technische Entwickler- und Betriebsdokumentation.

**Nachpflegepflicht**: Bei Feature-Arbeit, die die Admin- oder Portalbedienung betrifft, die betroffene Seite im Docs-Repository aktualisieren bzw. die Lücke benennen. Bei neuen bedienungsrelevanten Flächen prüfen, ob eine neue Seite und ein `ROUTE_DOCS`-Eintrag nötig sind.

## Doku-Pflicht (Definition of Done)

**Eine Feature-Umsetzung oder ein Verhaltens-/Architekturwechsel gilt erst als abgeschlossen, wenn die betroffene Doku im Repo mitgezogen wurde — das ist kein optionaler Nachputz-Schritt, sondern Teil der Aufgabe selbst.** Vor der Abschlussmeldung an Karl prüfen, nicht danach:

1. `almanac/` — betroffene Seiten identifizieren (Pfad steht meist schon in `sources:` im Frontmatter) und gegen den tatsächlichen Code korrigieren. Nicht nur ergänzen: veraltete Aussagen (alte Architektur, entfernte Fallbacks, "geplant für später" bei Dingen, die jetzt gebaut sind) explizit korrigieren oder streichen.
2. `katalon-collections/katalon-docs` — nur wenn das Feature Admin- oder Portalbedienung betrifft, die Kuratoren/Sachbearbeiter direkt sehen. Neue bedienungsrelevante Fläche → prüfen, ob eine neue Seite und ein `ROUTE_DOCS`-Eintrag (`Topbar.tsx`) nötig ist.
3. `.agents/knowledge/decisions/` (dev-only, nicht Teil des Git-Repos) — bei echter Architekturentscheidung (neue Komponente, Trade-off, Abweichung von bestehendem Muster) neues Konzept anlegen und in `decisions/index.md` verlinken.
4. Externe Anwenderdokumentation (`katalon-collections/katalon-docs`) — im Docs-Repository pflegen und über GitHub Pages veröffentlichen.

Ist eine Doku-Anpassung aus Zeit-/Scope-Gründen bewusst zurückgestellt: das explizit benennen ("Doku X ist jetzt veraltet, noch nicht nachgezogen"), nicht stillschweigend weglassen. Ein Feature ohne diesen Schritt ist unvollständig geliefert, selbst wenn Code und Tests grün sind.

## CodeAlmanac

Vor jeder Umsetzung die relevanten CodeAlmanac-Seiten konsultieren und den Plan auf Widersprüche prüfen. Zusätzlich mögliche UX-Einwände gegen `PRODUCT.md` und `DESIGN.md` prüfen und vor der Umsetzung benennen; auch technisch getriebene Features auf Auswirkungen für Bedienung, Accessibility, Fehlerzustände und Responsive-Verhalten prüfen.

Nach Implementierungen, die dokumentiertes Verhalten, Abläufe oder Architektur ändern, `almanac/` aktualisieren und die betroffenen Seiten gegen den tatsächlichen Code verifizieren. Veraltete Seiten korrigieren oder kennzeichnen; rein aus dem Code ablesbare Details nicht duplizieren. Siehe "Doku-Pflicht" oben — das ist keine Kann-Empfehlung.

## Kontext-Dateien — Lazy Loading

Lebende Prozess-/Produkt-Dokumente bleiben an ihrem Ort (nicht Teil von `.agents/knowledge/`, siehe oben), werden aber nur bei Bedarf gelesen statt pauschal vorausgesetzt:

- Frage zu Roadmap, Phasenstatus, offenen Issues, Priorität → GitHub-Issues (Roadmap-Umbrellas #260–#267)
- Frage zu lokalem Setup, Dev-Workflow, Docker-Stack-Wahl → `.agents/DEV.md`
- Frage zum Datenmodell im Detail (über die Kurzfassung hier hinaus) → `KONZEPT.md`
- UI-/UX-/Produktentscheidung, Zielgruppe, Design-Prinzipien → `PRODUCT.md` + `DESIGN.md`

## Coding Rules — Lazy Loading

Sprachspezifische Coding-Regeln liegen nicht hier, sondern in `.agents/rules/`, und werden nur bei Bedarf geladen:

- Wird `backend/` angefasst → vorher `.agents/rules/backend.md` lesen.
- Wird `frontend/admin/` oder `frontend/portal/` angefasst → vorher `.agents/rules/frontend.md` lesen.
- Beide betroffen (siehe Full-Stack Exploration Rule unten) → beide Dateien lesen.

## Admin-I18n

Jede neue oder geänderte sichtbare Zeichenkette in der Admin-UI muss auf Deutsch und Englisch vorliegen. Keine fest kodierten UI-Texte nur für eine Sprache ergänzen.

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

**Regel: Bei jeder echten programmatischen Änderung die Patch-Version hochziehen** (`0.1.0` → `0.1.1` → `0.1.2` …).

Reine Dokumentation, Agent-Anweisungen, Metadaten oder Lockfile-Nachzüge ohne Programmänderung brauchen keinen Versions-Bump, kein Release-Tag und keine vollständige Testsuite. Diff-Check genügt; weitergehende Verifikation nur auf ausdrücklichen Wunsch.

Dazu bei jedem Commit:
1. `backend/pyproject.toml` — `version = "x.y.z"`
2. `frontend/admin/package.json` — `"version": "x.y.z"`
3. `frontend/portal/package.json` — `"version": "x.y.z"`
4. `CHANGELOG.md` — neuen Eintrag unter `[Unreleased]` oder neuen `[x.y.z]`-Block
5. Nach dem Commit: `git tag vx.y.z && git push origin vx.y.z`

**Minor-Bump** (`0.1.x` → `0.2.0`): neue Features oder abgeschlossene Phase → kurz informieren, Karl entscheidet.
**Major-Bump** (`0.x.y` → `1.0.0`): erster öffentlicher Release → explizite Absprache.

Jeder `git push origin vX.Y.Z` löst `.github/workflows/release-metadata.yml` aus: generiert `katalon-release.json` (via `scripts/gen_release_metadata.py`) und hängt es als Asset an den GitHub-Release. Das ist die Metadatenquelle, die `katalon-cli` für Updates/Kompatibilitätschecks konsumiert.

## GitHub-Issues — Pflege

Wird ein Feature oder Bugfix umgesetzt, das ein offenes GitHub-Issue betrifft:

1. Prüfen, ob das Issue durch den Commit/PR vollständig erledigt ist.
2. Bei vollständiger Umsetzung das Issue schließen und im Kommentar den entscheidenden Commit oder PR referenzieren.
3. Falls nur ein Teil erledigt ist: Issue aktualisieren, erledigte Checkboxen markieren und offenen Rest beschreiben.
4. Issues nicht einfach offen stehen lassen, wenn der Code längst im Main-Branch ist.

## Feature-Kommunikation

Bei jedem echten neuen Feature (nicht bei Bugfixes, Refactorings oder rein technischen Änderungen) nach der Umsetzung einen kurzen, eigenständig versendbaren Text für Nicht-Techniker ausgeben. Er erklärt in klarer Sprache, was neu ist und welchen praktischen Nutzen es bringt; technische Details nur, wenn sie für die Nutzung wichtig sind. Der Text soll direkt als E-Mail-Absatz verwendbar sein.

## Production-Installation (katalon-cli)

Production-Instanzen werden nicht aus diesem Repo geklont/gebaut, sondern über die separate CLI `katalon-cli` (`github.com/karkraeg/katalon-cli`, `uv tool install katalon-cli`) installiert/aktualisiert — sie pullt gepinnte Release-Images statt Source-Checkout. `install.sh` und `docker-compose.dev.yml` bleiben unverändert für lokale Entwicklung.

`release-meta.toml` in diesem Repo (compose_revision, minimum_installer_version, requires) manuell pflegen, wenn sich Compose-Topologie oder CLI-Anforderungen ändern — siehe Kommentar in der Datei.

Details/Architektur: `almanac/decisions/operations/katalon-cli-distribution.md`, GitHub-Issue [#286](https://github.com/karkraeg/Katalon/issues/286).

## Nächster logischer Schritt

Siehe die GitHub Roadmap (Issues #260–#267) für aktuelle Prioritäten.
