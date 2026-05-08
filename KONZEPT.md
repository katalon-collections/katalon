# Projektkonzept: Katalon
**Eine moderne Sammlungsdatenbank für den GLAM-Sektor**

---

## 1. Die Motivation

### Was Katalon ist

Katalon ist eine **Sammlungsdatenbank** für Galerien, Bibliotheken, Archive und Museen (GLAM). Das Kernversprechen: frei konfigurierbare Metadaten für physische und digitale Sammlungsobjekte, Personen, Orte und Ereignisse — mit einem öffentlichen Discovery-Portal und einer sauberen REST-API.

Der direkte Vorläufer ist **CollectiveAccess**, das über Jahrzehnte bewiesen hat, dass ein flexibles Metadatenschema (*Configuration over Coding*) der richtige Ansatz ist. Dennoch leidet es unter massiver Legacy-Last:

- Monolithische PHP-Architektur, schwer wartbar und erweiterbar
- Komplexe XML-Konfigurationen mit hoher Einstiegshürde
- Schlechte API – keine moderne Frontend-Integration möglich
- Keine native Python/Datenscience-Integration

**Katalon** überführt die Flexibilität in Python + React: dynamische Schemata, kontrollierte Vokabulare, Entitätsrelationen – aber mit einer sauberen REST-API, zwei React-Frontends und einer modernen Deployment-Infrastruktur.

### Was Katalon nicht ist

Katalon ist **kein Bibliothekssystem**. Es gibt kein MARC-Datenmodell, keine Exemplarverwaltung, keinen Ausleihverkehr, keine Z39.50-Schnittstelle. Wer einen OPAC oder ein Bibliotheksintegrationssystem sucht, braucht Koha, FOLIO oder ähnliches.

Katalon ist auch **kein institutionelles Repositorium** im Sinne von DSpace oder InvenioRDM — kein Einreichungs-Workflow, kein Embargo-Management, kein DOI-Minting. Ein flexibles Schema kann zwar born-digital Dokumente beschreiben (PDF-Anhänge, Reports, Forschungsdaten), aber das ist ein sekundärer Anwendungsfall, kein Kernversprechen.

**Der Fokus liegt auf Sammlungsobjekten:** Fotografien, Kunstwerke, Archivmaterialien, archäologische Funde, Naturalienkabinette, Instrumente — und allem, was dazu gehört (wer hat es gemacht, wo war es, was zeigt es).

---

## 2. Die User Story: Das Marokko-Archiv (1900–1950)

Ein Sammler besitzt tausende historische Fotografien aus Marokko. Sein Ziel:
1. **Individuelle Metadaten** definieren (Ort inkl. Koordinaten, Kameratyp, Fotograf als Entität).
2. **Bestandsdaten** aus alten Excel-Listen ohne Datenverlust importieren.
3. **Digitalisate** lokal speichern und in einem hochauflösenden **IIIF-Viewer** (Deep Zoom) der Öffentlichkeit zugänglich machen.
4. **Sichtbarkeit** steuern (intern vs. öffentlich).

---

## 3. Architektur: Headless mit zwei Frontends

```
┌─────────────────┐    ┌─────────────────┐
│   Admin-UI      │    │  Public-Portal  │
│  (React/Vite)   │    │  (React/Vite)   │
│  Eingabe, CRUD  │    │  Suche, IIIF    │
└────────┬────────┘    └────────┬────────┘
         │                     │
         └──────────┬──────────┘
                    │ REST/JSON
         ┌──────────▼──────────┐
         │   FastAPI Backend   │
         │   (Python 3.12+)    │
         └──────────┬──────────┘
                    │
       ┌────────────┼────────────┐
       ▼            ▼            ▼
  PostgreSQL  Elasticsearch  Cantaloupe
  +PostGIS    (Suche)        (IIIF)
  +JSONB
```

---

## 4. Technischer Stack

| Komponente | Technologie |
|---|---|
| API Framework | FastAPI (Python 3.12+) |
| Datenbank | PostgreSQL 16 + PostGIS + JSONB |
| Suche | Elasticsearch 8.x |
| Bildserver | Cantaloupe (IIIF Image API) |
| Task Queue | Celery + Redis |
| Storage | Lokales Dateisystem (Bind Mount, konfigurierbar) |
| Admin-UI | React + TypeScript (Vite) |
| Public-Portal | React + TypeScript (Vite) |
| Deployment | Docker Compose |

---

## 5. Primärtypen

Katalon kennt vier gleichwertige Primärtypen. Alle haben **frei konfigurierbare Metadaten** (Schema-Engine gilt für alle Typen).

| Typ | Beschreibung | Beispiele |
|---|---|---|
| **Object** | Physische oder digitale Artefakte | Fotografie, Dokument, Gemälde, Born-Digital-PDF |
| **Entity** | Personen oder Organisationen | Fotograf, Verlag, Institution |
| **Place** | Geografische Orte mit Koordinaten | Stadtbezirk, Gebäude, Grabungsstätte |
| **Occurrence** | Ereignisse, abstrakte Werke und Konzepte | Ausstellung, Kampagne, Musikwerk, historisches Ereignis |

Typ-Hierarchien (Untertypen mit eigenen Pflichtfeldern) sind **Post-MVP**.

### Zur Herkunft des Begriffs „Occurrence"

„Occurrence" ist dem System **CollectiveAccess** entlehnt, wo es als Sammelbegriff für alles gilt, das kein Objekt, keine Entität und kein Ort ist. Es ist kein Industriestandard — der internationale Referenzrahmen **CIDOC-CRM** (ISO 21127) nennt das entsprechende Konzept *E5 Event*, kommerzielle Systeme wie Axiell/EMu verwenden ebenfalls „Event".

„Event" wäre intuitiver, aber zu eng: Eine Ausstellung ist ein Ereignis, ein abstraktes Werk im Sinne der *Functional Requirements for Bibliographic Records* (FRBR) — also „Beethovens 9. Sinfonie" als intellektuelle Schöpfung unabhängig von Aufnahmen oder Noten — ist keins. Dafür kennt CIDOC-CRM eine eigene Klasse (*E28 Conceptual Object*). Katalon fasst beides unter Occurrence zusammen.

**Praktische Faustregel:**
- Ist es ein konkretes Ding mit einer Datei, einer Inventarnummer oder einem physischen Standort → **Object**
- Ist es eine Person oder Organisation → **Entity**
- Ist es ein Ort → **Place**
- Ist es ein Ereignis, eine Ausstellung, ein Werk, eine Kampagne, ein Konzept — also etwas, das die anderen drei verbindet oder kontextualisiert → **Occurrence**

Wie Objects mit `object_type` und Entities mit `entity_type` hat auch Occurrence ein `occurrence_type`-Feld. Institutionen legen eigene Untertypen an und benennen sie frei: „Werk", „Komposition", „Ausstellung", „Grabungskampagne". Der Typ „Occurrence" selbst ist nicht umbenennbar — die Differenzierung geschieht ausschließlich über Untertypen.

---

## 6. Kernfunktionen

### 6.1 Dynamisches Schema-Management (pro Primärtyp)
- Admins definieren Felder über die Admin-UI, nicht über Code
- Feldtypen: Text, Datum (EDTF inkl. „um 1920"), Zahl, Geodaten, Dropdown (Vokabular), Boolean, Relation
- **Wiederholbare Felder:** Jedes Feld kann `is_repeatable: true` sein – mehrere Werte pro Datensatz
- Kontrollierte Vokabulare – hierarchisch, on-the-fly erweiterbar
- Schema lebt als JSONB in PostgreSQL → keine DB-Migrationen bei Schema-Änderungen

### 6.2 CRUD für alle Primärtypen
- Vollständiges Create/Read/Update/Delete für Objects, Entities, Places, Occurrences
- Sichtbarkeit: `draft` / `internal` / `public`
- Inventarnummer (`idno`) als eindeutige Kennung (bei Objects)

### 6.3 Relationen mit Metadaten
Alle vier Typen können miteinander verknüpft werden. Relationen selbst können Metadaten tragen:

```sql
relations (
    id UUID,
    from_type  VARCHAR,  -- object/entity/place/occurrence
    from_id    UUID,
    to_type    VARCHAR,
    to_id      UUID,
    relation_type VARCHAR,  -- z.B. "hat_fotografiert", "ist_aufgenommen_in"
    metadata   JSONB        -- z.B. {"role": "Auftraggeber", "date_range": "1923–1930"}
)
```

### 6.4 Kontrollierte Vokabulare
- Hierarchische Termlisten (z.B. Kameratypen, Genres, Materialien)
- On-the-fly erweiterbar während der Erfassung
- Pro Feld zuweisbar

### 6.5 Medien & IIIF
- Upload von Bilddateien (Phase 1: Bilder)
- Asynchrone Tile-Generierung via Celery → Cantaloupe (IIIF Image API 3)
- IIIF-Manifest pro Object → Deep Zoom im Public-Portal (OpenSeadragon)

### 6.6 Audit Log
Vollständiges Änderungsprotokoll – wer hat was wann geändert:

```sql
audit_log (
    id           UUID,
    record_type  VARCHAR,    -- object/entity/place/occurrence
    record_id    UUID,
    user_id      UUID,
    action       VARCHAR,    -- create/update/delete
    changed_fields JSONB,   -- {"title": ["alt", "neu"]}
    created_at   TIMESTAMPTZ
)
```

### 6.7 Versionierung (Snapshots)
Manuelles Speichern eines benannten Zustands als referenzierbare Version:

```sql
record_snapshots (
    id           UUID,
    record_type  VARCHAR,
    record_id    UUID,
    label        VARCHAR,    -- z.B. "Abgabe ans Museum 2024-03"
    snapshot     JSONB,      -- vollständiger Datensatz-Zustand
    created_by   UUID,
    created_at   TIMESTAMPTZ
)
```

### 6.8 Authority-Plugin-System
Plugin-Architektur für externe Normdatenquellen (GND, VIAF, Geonames, …):

```python
class AuthoritySource(ABC):
    id: str                  # z.B. "gnd", "viaf"
    label: str
    def search(self, query: str) -> list[AuthorityResult]: ...
    def fetch(self, identifier: str) -> AuthorityRecord: ...
```

- Adapter werden als Python-Packages registriert
- Admin-UI: „Von GND übernehmen" – Suche, Vorschau, Import in lokale Entität
- Anbindung: REST-API, SRU, SPARQL je nach Quelle

### 6.9 Smart Importer (ETL)
- Excel/CSV-Import mit visuellem Spalten-Mapping
- Regelwerk: Split bei Trennzeichen, Formatnormalisierung
- Dry Run mit Fehler-Report vor echtem Import

### 6.10 Suche & Discovery
- Elasticsearch: Volltext + Facetten für alle Primärtypen
- Öffentlicher, unauthentifizierter Such-Endpunkt

### 6.11 OAI-PMH
- Harvesting-Protokoll für Deutsche Digitale Bibliothek u.a.
- Dublin Core Mapping konfigurierbar

---

## 7. Datenmodell

### 7.1 Primärtypen (alle mit JSONB-Metadaten)

```sql
-- Generische Basisstruktur für alle Typen
objects (
    id UUID PRIMARY KEY,
    idno VARCHAR UNIQUE,
    status VARCHAR(20),         -- draft/internal/public
    metadata JSONB,             -- alle dynamischen Felder (auch repeatable als Arrays)
    search_vector TSVECTOR,
    created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ
)

entities (
    id UUID PRIMARY KEY,
    entity_type VARCHAR(50),    -- person/organization
    status VARCHAR(20),
    metadata JSONB,
    search_vector TSVECTOR,
    created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ
)

places (
    id UUID PRIMARY KEY,
    geom GEOMETRY(Point, 4326), -- PostGIS
    status VARCHAR(20),
    metadata JSONB,
    search_vector TSVECTOR,
    created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ
)

occurrences (
    id UUID PRIMARY KEY,
    occurrence_type VARCHAR(50), -- work/event/concept/...
    status VARCHAR(20),
    metadata JSONB,
    search_vector TSVECTOR,
    created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ
)
```

### 7.2 Schema-Definitionen (pro Primärtyp)

```sql
field_definitions (
    id UUID PRIMARY KEY,
    target_type  VARCHAR(20),   -- object/entity/place/occurrence
    name         VARCHAR(100),
    label        JSONB,         -- {"de": "Titel", "en": "Title"}
    field_type   VARCHAR(50),   -- text/date/number/geo/vocab/relation/boolean
    is_required  BOOLEAN,
    is_repeatable BOOLEAN,
    sort_order   INT,
    settings     JSONB          -- feldtyp-spezifische Optionen
)
```

### 7.3 Relationen (generisch, mit Metadaten)

```sql
relations (
    id            UUID PRIMARY KEY,
    from_type     VARCHAR(20),
    from_id       UUID,
    to_type       VARCHAR(20),
    to_id         UUID,
    relation_type VARCHAR(100),
    metadata      JSONB,
    created_at    TIMESTAMPTZ
)
```

### 7.4 Vokabulare

```sql
vocabularies (id UUID, name VARCHAR, is_hierarchical BOOLEAN)
vocabulary_terms (id UUID, vocabulary_id UUID, term VARCHAR, label JSONB, parent_id UUID)
```

### 7.5 Medien

```sql
media_files (
    id UUID, object_id UUID, filename VARCHAR,
    mime_type VARCHAR, file_path TEXT,
    iiif_manifest JSONB, status VARCHAR
)
```

### 7.6 Audit Log & Snapshots

```sql
audit_log (
    id UUID, record_type VARCHAR, record_id UUID,
    user_id UUID, action VARCHAR,
    changed_fields JSONB, created_at TIMESTAMPTZ
)

record_snapshots (
    id UUID, record_type VARCHAR, record_id UUID,
    label VARCHAR, snapshot JSONB,
    created_by UUID, created_at TIMESTAMPTZ
)
```

### 7.7 Authority-Quellen

```sql
authority_sources (
    id VARCHAR PRIMARY KEY,     -- "gnd", "viaf"
    label VARCHAR,
    adapter_class VARCHAR,      -- Python-Klassenpfad
    config JSONB,               -- API-Keys, Base-URLs usw.
    is_enabled BOOLEAN
)
```

---

## 8. Wiederholbare Felder – JSONB-Struktur

Einfaches Feld:
```json
{"title": "Straße in Marrakesch"}
```

Wiederholbares Feld:
```json
{
  "title": [
    {"value": "Straße in Marrakesch", "lang": "de"},
    {"value": "Street in Marrakech", "lang": "en"}
  ],
  "photographer": [
    {"entity_id": "uuid-1", "role": "Auftraggeber"},
    {"entity_id": "uuid-2", "role": "Techniker"}
  ]
}
```

---

## 9. Phasenplan

| Phase | Meilenstein | Scope |
|---|---|---|
| 0–1 | Infra (Docker Compose) + Core-Datenbank (alle 4 Typen + Relationen) | Infra/Backend |
| 2 | Schema-Engine (field_definitions für alle Typen, repeatable, Vokabulare) | Backend |
| 3 | CRUD für alle 4 Primärtypen + Relationen mit Metadaten | Backend |
| 4 | Auth (FastAPI-Users, JWT, Rollen) + Audit Log | Backend |
| 5 | Media & IIIF (Upload, Celery, Cantaloupe, Manifest) | Backend ← MVP-API |
| 6 | Admin-UI: Schema + CRUD + Medien | Frontend ← MVP |
| 7 | Elasticsearch + Versionierung (Snapshots) | Backend |
| 8 | Public-Portal: Suche, Facetten, IIIF-Viewer | Frontend |
| 9 | Authority-Plugin-System + erste Adapter (GND, Geonames) | Backend+Frontend |
| 10 | Smart Importer (ETL) | Full-Stack |
| 11 | OAI-PMH | Backend |
| 12 | Hardening | Infra |

**MVP = Phasen 0–6** (vollständiges System mit Admin-UI, alle 4 Typen, Relationen, IIIF).

---

## 10. Docker Compose

```yaml
services:
  api:          # FastAPI Backend
  worker:       # Celery Worker (Bildverarbeitung, Index-Sync)
  db:           # PostgreSQL 16 + PostGIS
  elasticsearch:
  redis:
  cantaloupe:   # IIIF Image Server
  admin:        # React Admin-UI
  portal:       # React Public-Portal
  nginx:        # Reverse Proxy
```

---

## 11. Theme-System für das Discovery-Portal (Post-MVP)

Das Public-Portal soll vollständig themebar sein — ohne Code-Änderungen, ohne Build-Prozess auf Seite der Institution.

### Ziel

Institutionen können das Aussehen des Discovery-Portals (Farben, Typo, Layout-Varianten, Logo, Favicon) durch ein **Theme-Bundle** komplett ändern. Das Admin-UI bleibt immer einheitlich (kein Theming nötig).

### Theme-Bundle-Struktur

Ein Theme ist ein einzelnes Verzeichnis, das per Drop-in installiert wird:

```
themes/
└── mein-archiv/
    ├── theme.json        ← Metadaten + Design-Tokens (Pflicht)
    ├── logo.svg          ← Logo (optional)
    ├── favicon.ico       ← Favicon (optional)
    ├── custom.css        ← CSS-Overrides (lädt nach Base-CSS, optional)
    └── preview.png       ← Vorschaubild für Theme-Auswahl (optional)
```

**`theme.json` Beispiel:**
```json
{
  "name": "Stadtarchiv Basel",
  "version": "1.0.0",
  "author": "Stadtarchiv Basel",
  "tokens": {
    "--accent":    "#8b2635",
    "--accent-50": "#fdf2f3",
    "--accent-ink":"#6b1c28",
    "--bg":        "#f8f6f1",
    "--panel":     "#ffffff",
    "--fg":        "#1a1208",
    "--sb-bg":     "#2c1810",
    "--sb-fg":     "#e8ddd5"
  },
  "fonts": {
    "body": "https://fonts.googleapis.com/css2?family=Libre+Baskerville:wght@400;700&display=swap",
    "mono": null
  },
  "logo": "logo.svg",
  "favicon": "favicon.ico"
}
```

### Installation (Drop-in, kein Rebuild)

```bash
# Theme ins Daten-Volume legen
cp -r mein-archiv/ /var/lib/katalon/themes/mein-archiv/

# Aktives Theme in .env setzen
PORTAL_THEME=mein-archiv

# Docker-Container neu starten (kein Build nötig)
docker compose restart portal
```

Das Portal liest `theme.json` beim Start via `GET /v1/theme` und injiziert die Tokens als CSS Custom Properties in `<head>`. Kein Vite-Build, kein Node auf dem Server nötig.

### Technische Umsetzung (Portal)

```
frontend/portal/src/theme/
├── loader.ts     ← lädt theme.json via API
├── inject.ts     ← setzt CSS-Variablen auf :root vor erstem Paint
└── defaults.ts   ← Fallback-Tokens (Katalon-Standard)

/var/lib/katalon/themes/   ← Docker volume, per symlink als /public/themes erreichbar
```

Backend-Endpunkt: `GET /v1/theme` → liefert aktives `theme.json` + URLs zu Logo/CSS.

### Was Themes steuern können

| Bereich | Beispiele |
|---|---|
| Farben | Akzent, Hintergrund, Text, Sidebar, Badges |
| Typografie | Google Fonts URL oder lokale Schrift |
| Branding | Logo (SVG/PNG), Favicon |
| CSS-Overrides | Alles Weitere via `custom.css` |

### Bewusste Einschränkungen

- **Kein JavaScript** im Theme (Sicherheit)
- Kein Einfluss auf Suchlogik oder Datenstruktur
- Admin-UI ist nicht themebar (einheitliches Werkzeug)

---

## 12. Nicht im Scope

### Nie im Scope

- Bibliotheks-OPAC, MARC, Exemplarverwaltung, Ausleihverkehr
- Video/Audio-Transcoding
- Leihverkehr / Standortverwaltung
- Z39.50, SRU-Server (Harvesting via OAI-PMH ist im Scope)

### Post-MVP (konzipiert, aber noch nicht gebaut)

- Theme-System Discovery-Portal (Konzept → Abschnitt 11)
- Typ-Hierarchien (Untertypen mit eigenen Pflichtfeldern)
- Sets / Konvolute
- S3 / Object Storage (→ Issue #121)
- Chunked Upload für Dateien >100 MB (→ Issue #120)
- PDF- und weitere Medientypen (→ Issues #123, #125)
- Kartenansicht / Radius-Suche für Orte (→ Issue #124)
- „Register in place" (Medien ohne Kopieren verknüpfen, → Issue #122)
