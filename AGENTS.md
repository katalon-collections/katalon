# Katalon – gemeinsame Agent-Regeln

## Geltung und lokale Ergänzung

Diese Datei enthält die gemeinsamen Regeln für Beiträge und Coding-Agents.
`CLAUDE.md` ist ein Symlink auf diese Datei.

**Vor Beginn der Arbeit:** Prüfe, ob `.agents/maintainer/AGENTS.md` vorhanden ist.
Falls ja, lies diese Datei vollständig und beachte ihre ergänzenden Regeln für
den privaten Maintainer-Checkout. Das ist ein ausdrücklicher Leseauftrag dieser
Datei, keine automatische Erkennung beliebiger Unterverzeichnisse. Ohne diese
Ergänzung gilt der gemeinsame Beitragsworkflow uneingeschränkt. Die Ergänzung
ändert keine Projektverträge und darf keine Sicherheitsgrenzen abschwächen.

## Was ist dieses Projekt?

Katalon ist ein Open-Source Metadata Management System (MMS) für den GLAM-Sektor (Galleries, Libraries, Archives, Museums), gebaut mit Python/FastAPI-Backend und React-Frontends.
 
**Betriebsmodell und Verantwortlichkeiten:** Katalon ist selbst betriebene Open-Source-Software, kein zentral gehostetes Produkt. Es ist Open-Source-Software, die Institutionen in ihrer eigenen Infrastruktur selbst installieren, betreiben und absichern. Die jeweilige Betreiberinstitution ist für Datenschutz und rechtliche Anforderungen, Zugriffsschutz, Updates, Monitoring, Back-ups, Wiederherstellung, Verfügbarkeit und die Sicherheit ihrer Daten und ihres Betriebs verantwortlich. Antworten und Implementierungen dürfen keine zentralen Betriebsleistungen des Projekts für Nutzer voraussetzen.

**Lizenz:** AGPL-3.0-or-later (`LICENSE`). Jede Code-Datei (Backend `.py`, Frontend `.ts`/`.tsx`, E2E-Tests) trägt einen SPDX-Header (`SPDX-License-Identifier: AGPL-3.0-or-later` + `Copyright (c) 2026 Karl Krägelin`) — neue Dateien bekommen denselben Header. Details/Begründung: `almanac/decisions/operations/license-and-branding.md`.

**Name:** Extern (Browser-Titel, Login-Screen, README, "Über Katalon"-Seite in der Admin-UI) heißt die Software **"Katalon Collections"** — Abgrenzung zum unabhängigen Produkt katalon.com. Intern (Code, Packages, Repo-Name, Admin-Sidebar/Breadcrumbs, alle Doku-Dateien in diesem Repo) bleibt es kurz **"Katalon"**. Keine Code-Identifier umbenennen.

**Design-Ziele:**

- Schema-Konfiguration über die Oberfläche statt über Konfigurationsdateien
- Saubere REST-API für moderne Frontends und Integrationen
- Native Python/Datenscience-Integration

## Dateien in diesem Verzeichnis

- `KONZEPT.md` – vollständiges Konzeptdokument mit Datenmodell
- Tracker des jeweiligen Repositorys – Phasenstatus, Prioritäten und offene Arbeit
- `.agents/DEV.md` – Entwickler-Setup und Workflows
- `docs/` – technische Entwickler- und Betriebsdokumentation
- `e2e/` – Playwright-E2E-Tests

## Fixierte Architekturentscheidungen

| Entscheidung     | Festgelegt                                                 |
|------------------|------------------------------------------------------------|
| Name             | **Katalon**                    |
| Backend          | Python 3.14+ / FastAPI                                     |
| Datenbank        | PostgreSQL 16 + PostGIS + JSONB                            |
| Suche            | Elasticsearch 8.x                                          |
| Bildserver       | Cantaloupe (IIIF Image API 3)                              |
| Task Queue       | Celery + Redis                                             |
| Frontend         | React + TypeScript (Vite) – zwei separate Apps             |
| Deployment       | Docker Compose                                             |
| IIIF im MVP      | Ja                                                         |
| Sieben Kerntypen | Getrennte Tabellen für Bestands-, Sammlungs-, Standort- und Vorgangsdaten (siehe unten) |

## Export: aggregator-agnostisch

Der Export-Kern (Formate, Builder, Prüfungen, OAI-PMH, Admin-Mapping-Editor) kennt **keinen bestimmten Aggregator** (DDB, Europeana, Kalliope, …). Anforderungen eines Aggregators werden ausschließlich als Konfiguration abgebildet: Mapping-Regeln, Regel-Settings und `institution_config` (z. B. erlaubte Lizenz-URIs als Liste, Pflichtprüfungen als Schalter), portabel per YAML. Aggregatorspezifisches gehört in Beispiel-Mappings, Doku-Rezepte oder Test-Fixtures, nicht in Code-Pfade, Konstanten, Schlüsselnamen (`profile: ddb`) oder UI-Beschriftungen. Gilt auch für Defaults: Eine Schreibweise oder Liste, die nur ein Aggregator verlangt, ist kein Kern-Default.

## Kerntypen (`RECORD_TYPES`)

Katalon unterscheidet 7 eigenständige Datensatztypen mit jeweils eigener DB-Tabelle, optimistischer Sperre (`version`), Zeitstempeln und frei konfigurierbaren Metadaten (`field_definitions` via JSONB):

### Bestands- & Sammlungsdaten (Inventory & Collections)

| Typ | DB-Tabelle | Beschreibung |
|---|---|---|
| `object` | `objects` | Artefakte: Fotos, Dokumente, Gemälde, Digitalisate |
| `entity` | `entities` | Personen, Körperschaften / Organisationen |
| `place` | `places` | Geografische Orte (PostGIS-Punktgeometrie) |
| `occurrence` | `occurrences` | Werke (FRBR), Ereignisse, Ausstellungen, Konzepte |
| `collection` | `collections` | Sammlungen, Bestände, Archivtektonik (hierarchisch via `parent_id`) |

### Standortverwaltung & Logistik (Internal Logistics)

| Typ | DB-Tabelle | Beschreibung |
|---|---|---|
| `storage_location` | `storage_locations` | Lagerorte/Standorte (hierarchisch via `parent_id`: Gebäude → Raum → Regal → Fach). Rein intern/sicherheitsrelevant, wird nicht im Portal publiziert. |

### Vorgänge (Procedures / Process)

| Typ | DB-Tabelle | Beschreibung |
|---|---|---|
| `procedure` | `procedures` | Vorgänge: Leihverkehr, Erwerbung, Restaurierung (eigene Prozessfelder für Fristen, Aktenzeichen, Status). |

Zusätzlich unterstützt die Schema-Engine `vocabulary_term` als erweiterten Zieltyp (`SCHEMA_TARGET_TYPES`), um Terme in kontrollierten Vokabularen mit benutzerdefinierten Feldern zu versehen.

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
├── AGENTS.md              # diese Datei (CLAUDE.md ist Symlink hierauf)
```

## Schlüsselentscheidungen Datenmodell

### Schema-Engine (gilt für alle Typen)

```sql
field_definitions (
    id UUID, target_type VARCHAR,  -- object/entity/place/occurrence/procedure/collection/storage_location/vocabulary_term
    name VARCHAR, label JSONB,     -- {"de": "...", "en": "..."}
    field_type VARCHAR,            -- text/date/number/geo/vocab/relation/boolean/group/...
    is_required BOOLEAN, is_repeatable BOOLEAN,
    sort_order INT, settings JSONB
)
```

### Wiederholbare Felder (JSONB-Arrays)

```json
{
  "title": ["Straße in Marrakesch", "Weitere Bezeichnung"],
  "photographer": [{"id": "uuid-1", "label": "Person A", "relation_type": "photographer"}]
}
```

Übersetzbare Textwerte sind Sprach-Dicts (`{"de": "Titel", "en": "Title"}`),
unabhängig davon, ob das Feld wiederholbar ist.

### Relationen (generisch, mit Metadaten auf der Relation)

```sql
relations (
    id UUID, from_type VARCHAR, from_id UUID,
    to_type VARCHAR, to_id UUID,
    relation_type VARCHAR, metadata JSONB
)
```

Alle 7 Datensatztypen können über die `relations`-Tabelle beliebig typübergreifend verknüpft werden (z. B. Object ↔ Entity, Object ↔ Collection via `member_of`, Object ↔ StorageLocation via `normal_location`/`current_location`).

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

## Beitragsworkflow und Konzeption

[CONTRIBUTING.md](CONTRIBUTING.md) beschreibt Setup, Beiträge und Prüfungen.
Kleine, klar begrenzte Korrekturen können direkt als PR vorbereitet werden.
Neue größere Funktionen und Architekturänderungen werden vor der Implementierung
mit dem Maintainer im zum Repository passenden Issue-/Vorschlagsprozess abgestimmt.
Private Tickets müssen für externe Beiträge nicht zugänglich sein.

Ein Konzept enthält Problem und Zielgruppe, bestehendes Verhalten, Lösungsansatz,
Alternativen und Abwägung, Nicht-Ziele, betroffene Schnittstellen und Daten,
Risiken sowie Abnahmekriterien. Schema-/Datenänderungen erklären Migration und
Wiederherstellung; Berechtigungsänderungen erklären die Vertrauensgrenzen.

Bei Änderungen an sichtbaren Abläufen oder Informationsarchitektur gehören
Mockups, Wireframes oder ein begrenzter Prototyp dazu. Hauptablauf, leere und
Fehlerzustände, Tastaturbedienung und schmale Ansichten müssen erkennbar sein.
Bei rein technischen Architekturänderungen genügt ein passendes Komponenten-,
Datenfluss- oder Ablaufdiagramm. Konzept und visuelle Richtung werden vor der
größeren Umsetzung abgestimmt; ein kleines Bugfix braucht keinen eigenen Entwurf.

## Arbeitsweise, Sicherheit und Verifikation

- Lies geltende Regeln und relevante Verträge vor Änderungen. Prüfe bei Features
  Backendmodell/-Schema und die zugehörigen Frontendflächen, bevor du den Bestand bewertest.
- Nutze vorhandene Services und UI-Muster. Begrenze die Änderung auf den Auftrag,
  erhalte fremde Arbeitsstände und benenne Unsicherheiten oder widersprüchliche Anforderungen.
- Bei Fehlerberichten zuerst Logs des betroffenen Dienstes und einen reproduzierbaren
  Fall prüfen. Keine Lösung allein auf Basis einer Vermutung bauen.
- Neue Logik und Fehlerkorrekturen erhalten gezielte Regressionstests. Führe die
  betroffenen Backend-/Frontendprüfungen aus und dokumentiere deren Ergebnisse.
- Für UI-Änderungen visuelle und interaktive Prüfungen sowie die verwendete Umgebung
  angeben. Nicht durchgeführte Browser-/E2E-Abnahme als offen benennen. Die private
  Ergänzung kann festlegen, dass diese Abnahme durch den Maintainer erfolgt.
- Die vollständige Release-Prüfung ist ein eigener Gate; ein kleiner Fix braucht
  keine ungezielte Wiederholung sämtlicher Testläufe.
- Berechtigungen, öffentliche Projektion, Versionsprüfung und Datenintegrität
  gelten für jeden betroffenen Pfad. Bei wiederkehrenden Sicherheitsmustern
  weitere mögliche Fälle benennen und Such-/Fixumfang abstimmen; jeden betroffenen
  Pfad einzeln verifizieren.
- Keine Produktionsänderung, destruktive Datenoperation oder Veröffentlichung
  ohne Auftrag bzw. Freigabe der verantwortlichen Person. Secrets und
  vertrauliche Beispieldaten gehören nicht in Logs, Issues oder Commits.

## Python/uv Hinweise

- Backend-Python-Kommandos nach Möglichkeit aus `backend/` ausführen. **Ausnahme `katalon-manage`:** Die `DATABASE_URL` der `.env` nutzt den Docker-Host `db` (auf dem Host nicht auflösbar, `socket.gaierror`). Auf dem Host nur mit überschriebener `DATABASE_URL` (Dev-Stack: `@localhost:5432`) ausführen, sonst im Container: `docker compose exec api katalon-manage ...`. Das Repo-Root ist seit dem uv-Workspace (`pyproject.toml` mit `[tool.uv.workspace] members = ["backend"]`) für `uv run` aus dem Root nutzbar (z. B. `uv run katalon-manage`), `backend/.venv/bin/katalon-manage` (expliziter Interpreter) funktioniert ebenfalls. `Settings` liest `.env` seit der Source-Relokalisierung aus `backend/.env` bzw. Repo-Root (siehe `almanac/reference/operations/environment-and-secrets.md`).
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

**Regel:** Vor jeder Änderung an `docker/Dockerfile.admin`, `docker/nginx.admin.conf` oder `frontend/admin/vite.config.ts` explizit prüfen ob `VITE_BASE_PATH` und nginx-`location`-Blöcke konsistent sind. Nach einem beauftragten Deploy die Admin-URL der jeweiligen Instanz im Browser öffnen und JS/CSS-Requests in den DevTools prüfen.

## Datensicherheit – ABSOLUTE VERBOTE

**NIEMALS die Datenbank-Volumes löschen, neu erstellen oder `docker compose down -v` ausführen ohne explizite Bestätigung der verantwortlichen Person.** Das gilt auch dann, wenn es als schnelle Lösung erscheint (z. B. bei Passwort-Konflikten, Schema-Problemen oder Container-Fehlern). Datenverlust ist irreversibel.

Stattdessen bei DB-Problemen:
1. Logs lesen, Root Cause verstehen
2. Verantwortliche Person informieren und Optionen vorlegen
3. Erst nach ausdrücklicher Freigabe handeln

## Code Navigation und optionale Werkzeuge

CodeGraph kann Kontext, Aufrufbeziehungen und Änderungsfolgen liefern, wenn es
in der Umgebung vorhanden ist. Nutze die tatsächlich angebotenen Tools; Namen
und Fähigkeiten hängen von der Version ab. Ohne CodeGraph mit `rg`, Dateisuche
und gezieltem Lesen arbeiten. Ein privater Index oder MCP-Server ist keine
Voraussetzung für einen Beitrag; keinen Index ungefragt anlegen.

CodeAlmanac-CLI und OKF-Renderer sind optionale Ansichten/Prüfwerkzeuge. Die
Markdown-Dateien bleiben direkt lesbar. Falls ein Werkzeug fehlt, Inhalt und
lokale Verweise anhand der Dateien prüfen und den fehlenden automatischen Check
benennen. Das Fehlen eines Werkzeugs ersetzt nicht das Lesen relevanter Verträge.

## Dev Knowledge Base (OKF)

### Dokumentationszuständigkeit — gilt für alle Agents

OKF ist das Format der projektbezogenen Wissensbasis unter `.agents/knowledge/`; `decisions/` ist ein Teil davon. `.agents/decisions/` existiert nicht.

| Ablage | Maßgeblicher Inhalt |
|---|---|
| `.agents/knowledge/decisions/` | Warum: Entscheidung, Kontext, Alternativen, Abwägung, Konsequenzen und Status. Hier liegt die maßgebliche Entscheidungsakte. |
| `almanac/` | Wie: aktuelles Systemverhalten, Architektur, Datenflüsse, Verträge, Betrieb und Fallstricke, mit Belegen im aktuellen Code. `almanac/decisions/` enthält Zusammenfassungen und Umsetzungsstand mit Verweis auf die OKF-Akte; keine zweite unabhängige Entscheidungshistorie. |
| `.agents/DEV.md` | Entwickler-Einstieg: lokales Setup, Werkzeuge, Tests und Dokumentationswege. |
| `docs/` | Ausführliche technische Entwickler-/Betriebsanleitungen und ausdrücklich gekennzeichnete Konzepte/Audits. Almanac verlinkt sie, statt Anleitungen zu duplizieren. |
| Externes `katalon-docs` | Bedienungsanleitungen für Kuratoren und Sachbearbeiter; getrennt vom internen Entwicklungswissen. |

Vor Planung/Umsetzung die relevanten OKF-Entscheidungen und Almanac-Seiten lesen. Bei einer neuen oder geänderten Architekturentscheidung zuerst die OKF-Akte aktualisieren, danach betroffene Almanac-Verträge und technische Anleitungen. Bei einer reinen Verhaltensänderung ohne neue Architekturentscheidung nur die betroffene Verhaltensdokumentation nachziehen. Begründungen nicht in mehreren Ablagen unabhängig fortschreiben.

Vollständig abgelöste Entscheidungen und erledigte Planungsstände werden entfernt; weiterhin gültige Abwägungen bleiben als kurze aktuelle Entscheidungsakte erhalten. Kein separates Dokumentations-Pflegelog anlegen; Änderungen sind über Git nachvollziehbar. Ein Konzept ist kein Nachweis einer Implementierung. Bei Widersprüchen beschreibt der aktuelle Code das tatsächliche Verhalten; Abweichungen von einer gültigen Entscheidung benennen und klären, nicht stillschweigend als neue Entscheidung ausgeben.

OKF-Architecture/Playbooks/Gotchas bleiben kurze Einstiege oder historische Befunde mit Verweis auf die aktuelle Anleitung in Almanac/`docs/`. Die Pflegezuständigkeit folgt dem Inhalt, nicht dem Dateinamen.

Diese Regeln stehen im Root-`AGENTS.md`; `CLAUDE.md` verweist als Symlink darauf. Die optionale Ergänzung unter `.agents/maintainer/` bleibt ausschließlich im privaten Repository. Der öffentliche Export enthält `AGENTS.md`/`CLAUDE.md`, `CONTRIBUTING.md`, `.agents/` (ohne `.agents/maintainer/`) und `almanac/`. Details und Lesepfade: `.agents/DEV.md`.

`.agents/knowledge/` verwendet das [OKF-Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md). Lebende Prozess-/Produktdokumente bleiben an ihrem bestehenden Ort.

**Nachschlagen**: Bei Architektur-/Design-Fragen ("warum ist das so gebaut?") erst `.agents/knowledge/decisions/index.md` prüfen, bevor Code-Archäologie betrieben wird. Optionale lokale HTML-Ansicht: `make knowledge-site`; alternativ die Markdown-Dateien direkt lesen.

**Pflege**: Nach jeder Session, in der eine architektonisch relevante Entscheidung getroffen wird (neue Komponente, Trade-off zwischen Ansätzen, Abweichung von einem bestehenden Muster) — nicht bei reinen Bugfixes oder Feature-Implementierungen ohne Designfrage — ein neues Konzept unter `.agents/knowledge/decisions/` anlegen (Format wie bestehende Dateien: YAML-Frontmatter mit `type: Decision`, Sections Kontext/Entscheidung/Begründung/Citations) und in `decisions/index.md` verlinken.

## Anwender-Doku — Pflege

Die Anwenderdokumentation liegt in `katalon-collections/katalon-docs` und wird unter `https://katalon-collections.github.io/katalon-docs/` veröffentlicht. Die Admin-UI verlinkt ihre Hilfeziele direkt auf diese Seiten. `docs/` in diesem Repository enthält nur technische Entwickler- und Betriebsdokumentation.

**Nachpflegepflicht**: Jede Änderung, die die Admin- oder Portalbedienung betrifft (neue Funktion, geändertes Verhalten, neue oder umbenannte Beschriftungen, Fehlerkorrekturen mit sichtbarer Wirkung), zieht die betroffene Seite im Docs-Repository in derselben Aufgabe nach, auf Deutsch und Englisch (`src/content/docs/` und `src/content/docs/en/`). Ist das ausnahmsweise nicht möglich, die Lücke ausdrücklich benennen. Bei neuen bedienungsrelevanten Flächen prüfen, ob eine neue Seite und ein `ROUTE_DOCS`-Eintrag nötig sind.

**Docs-Repository beschaffen**: Das Docs-Repository liegt nicht in diesem Checkout. Vor der Doku-Änderung prüfen, ob es bereits neben diesem Repository liegt (üblich: `../katalon-docs`). Fehlt es, mit `git clone https://github.com/katalon-collections/katalon-docs.git ../katalon-docs` holen und dort auf einem eigenen Branch arbeiten. Ist das Klonen nicht möglich (kein Netz, keine Berechtigung, unklarer Ablageort), den User nach Pfad oder Zugang fragen, statt die Doku stillschweigend auszulassen. Für die Arbeit dort gelten die Regeln aus dessen `AGENTS.md`/`CLAUDE.md`.

**Versionsangabe**: Jeder neu dokumentierte Abschnitt (neue Funktion, Konfigurationsoption, Verhalten) bekommt dort eine Starlight-Hinweisbox `:::note[Verfügbar ab Version X.Y.Z]` mit der zum Zeitpunkt der Doku-Änderung aktuellen Version aus `backend/pyproject.toml` im öffentlichen Repo `katalon-collections/katalon` (nicht dem privaten `origin`). Konvention und Beispiele stehen in `AGENTS.md` von `katalon-collections/katalon-docs`.

## Doku-Pflicht (Definition of Done)

**Eine Feature-Umsetzung oder ein Verhaltens-/Architekturwechsel gilt erst als abgeschlossen, wenn die betroffene Doku im Repo mitgezogen wurde — das ist kein optionaler Nachputz-Schritt, sondern Teil der Aufgabe selbst.** Vor der Abschlussmeldung oder PR-Übergabe prüfen, nicht danach:

1. `almanac/` — betroffene Seiten identifizieren (Pfad steht meist schon in `sources:` im Frontmatter) und gegen den tatsächlichen Code korrigieren. Nicht nur ergänzen: veraltete Aussagen (alte Architektur, entfernte Fallbacks, "geplant für später" bei Dingen, die jetzt gebaut sind) explizit korrigieren oder streichen.
2. `katalon-collections/katalon-docs` — nur wenn das Feature Admin- oder Portalbedienung betrifft, die Kuratoren/Sachbearbeiter direkt sehen. Neue bedienungsrelevante Fläche → prüfen, ob eine neue Seite und ein `ROUTE_DOCS`-Eintrag (`Topbar.tsx`) nötig ist.
3. `.agents/knowledge/decisions/` (Projektentscheidungen) — bei echter Architekturentscheidung (neue Komponente, Trade-off, Abweichung von bestehendem Muster) neues Konzept anlegen und in `decisions/index.md` verlinken.
4. Externe Anwenderdokumentation (`katalon-collections/katalon-docs`) — im Docs-Repository pflegen und über GitHub Pages veröffentlichen.

Ist eine Doku-Anpassung aus Zeit-/Scope-Gründen bewusst zurückgestellt: das explizit benennen ("Doku X ist jetzt veraltet, noch nicht nachgezogen"), nicht stillschweigend weglassen. Ein Feature ohne diesen Schritt ist unvollständig geliefert, selbst wenn Code und Tests grün sind.

## CodeAlmanac

Vor jeder Umsetzung die relevanten CodeAlmanac-Seiten konsultieren und den Plan auf Widersprüche prüfen.

Nach Implementierungen, die dokumentiertes Verhalten, Abläufe oder Architektur ändern, `almanac/` aktualisieren und die betroffenen Seiten gegen den tatsächlichen Code verifizieren. Veraltete Seiten korrigieren oder kennzeichnen; rein aus dem Code ablesbare Details nicht duplizieren. Siehe "Doku-Pflicht" oben — das ist keine Kann-Empfehlung.

## Sparring, YAGNI & Devil's Advocate

Vor jeder Umsetzung aktiv mitdenken und als technischer und konzeptioneller Sparringspartner agieren – nicht als unkritischer Befehlsempfänger ("No Sycophancy"):

- **Devil's Advocate (aktiver Widerspruch):** Wenn eine Anforderung, ein Entwurf oder eine Architekturidee unnötig komplex, fehleranfällig, schwer rückbaubar oder inkonsistent zu bestehenden Prinzipien ist: **vor dem Schreiben von Code intervenieren**. Risiken, Trade-offs und schlankere Alternativen unaufgefordert auf den Tisch legen.
- **UX-Bedenken einbringen:** Mögliche Einwände gegen `PRODUCT.md` und `DESIGN.md` vorab prüfen und benennen. Auch technisch getriebene Features auf Auswirkungen für Bedienung, kognitive Last, Accessibility, Fehlerzustände und Responsive-Verhalten abklopfen.
- **YAGNI (You Aren't Gonna Need It) & Radikale Einfachheit:** Keine spekulativen Abstraktionen, Hook-/Plugin-Layer, generischen Konfigurationsoptionen oder "Zukunfts-Puffer" für Anforderungen bauen, die heute niemand braucht. Immer den direktesten, laziesten und wartungsärmsten Weg wählen, der das Problem zuverlässig löst ("Boring Technology").
- **Wiederverwendung vor Neubau:** Zuerst Standardbibliothek, vorhandene Schemata, Services und UI-Komponenten nutzen, bevor neue Tabellen, Endpoints, Abstraktionen oder Dependencies eingeführt werden. Wenn eine 20-Zeilen-Lösung reicht, kein Framework bauen.

## Kontext-Dateien — Lazy Loading

Lebende Prozess-/Produkt-Dokumente bleiben an ihrem Ort (nicht Teil von `.agents/knowledge/`, siehe oben), werden aber nur bei Bedarf gelesen statt pauschal vorausgesetzt:

- Frage zu Roadmap, Phasenstatus, offenen Issues, Priorität → zugänglicher Tracker des jeweiligen Repositorys; private Referenzen bei Bedarf im Vorschlag erklären
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
- Schema fields → `frontend/admin/src/components/screens/ScreenSchema.tsx`
- Record forms → `frontend/admin/src/components/screens/ScreenForm.tsx`
- Vocabularies → `frontend/admin/src/components/screens/ScreenVocab.tsx`
- Relations panel → `frontend/admin/src/components/screens/ScreenForm.tsx` (Beziehungen section)
- Public record view → `frontend/portal/src/`

## Versionierung, Review und Veröffentlichung

Katalon verwendet Semantic Versioning. Änderungen werden als zusammengehörige
PRs mit Problem, resultierendem Verhalten und Prüfbelegen eingereicht. Nutze
vollständige Issue-URLs, wenn Nummern zwischen Repositorys mehrdeutig sind;
verweise extern nicht auf eine nur privat verständliche Aufgabenbeschreibung.

Versionssprünge, Merge, Tags, Releases und Deployment werden vom Maintainer
koordiniert. Dafür ist die jeweilige Release-Prüfung erforderlich. Ein
Beitragsbranch erstellt keine Release-Tags und veröffentlicht keine Images.
Das private Maintainer-Repository kann parallel bestehen bleiben; Beiträge
werden in den festgelegten Entwicklungsprozess integriert.

Der öffentliche Stand wird durch einen kuratierten Source-Export erzeugt.
Private Commits oder Tags dürfen nicht direkt ins öffentliche Repository
gepusht werden. `.agents/maintainer/` und persönliche Sitzungsdateien dürfen
nicht im Export landen. Einzelheiten der privaten Remotes und Release-Schritte
liegen ausschließlich in der Maintainer-Ergänzung.

## Kommunikation von Änderungen

Beschreibe den praktischen Effekt neuer Funktionen auch für Nutzer ohne
technischen Hintergrund. Fehlerkorrekturen und interne Änderungen brauchen
keinen eigenen Feature-Text. Markiere manuelle Abnahme und zurückgestellte
Dokumentation ausdrücklich als offen.

## Production-Installation (katalon-cli)

Production-Instanzen werden nicht aus diesem Repo geklont/gebaut, sondern über die separate CLI `katalon-cli` (`github.com/katalon-collections/katalon-cli`, `uv tool install katalon-cli`) installiert/aktualisiert — sie pullt gepinnte Release-Images statt Source-Checkout. `install.sh` und `docker-compose.dev.yml` bleiben unverändert für lokale Entwicklung.

`release-meta.toml` in diesem Repo (compose_revision, minimum_installer_version, images, requires) manuell pflegen — siehe Kommentar in der Datei:

- **Das Katalon-Release bestimmt die Images der Fremdservices, nicht die CLI.** Postgres, Redis, Elasticsearch, Cantaloupe, nginx und Caddy stehen als `repository:tag` unter `[images]`; katalon-cli (ab 0.4.0) schreibt sie beim Update in `compose.yaml` und pullt sie. Keine Infrastruktur-Versionen ins CLI-Template schreiben.
- **Neue Version eines Fremdservice:** `[images]`, `docker-compose.yml` und `charts/katalon/values.yaml` gemeinsam ändern; `backend/tests/test_release_metadata.py` schlägt sonst fehl. Kein CLI-Release nötig.
- **`requires`** beschreibt, womit Katalon technisch läuft (gegen `[images]` getestet, von der CLI vor dem Update gegen die wirksamen Images inkl. `compose.override.yaml` geprüft). Bei neuer Mindestversion anheben.
- **Major-Wechsel von Postgres oder Elasticsearch** blockiert die CLI bewusst (Dump/Restore bzw. neues ES-Datenverzeichnis). Steht einer an, braucht es vorher einen Upgrade-Weg in katalon-cli — mit dem Maintainer abstimmen.
- **Neuer Service, Ports oder Volumes:** CLI-Template ändern, `compose_revision` und `minimum_installer_version` hochziehen.

Entscheidung: `.agents/knowledge/decisions/release-bestimmt-fremdservice-images.md`.

Details/Architektur: `almanac/decisions/operations/katalon-cli-distribution.md`.
