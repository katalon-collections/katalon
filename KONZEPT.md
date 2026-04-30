# Projektkonzept: Katalon
**Ein modernes Metadata Management System für den GLAM-Sektor**

---

## 1. Die Motivation

Die Archivwelt steht vor einem technologischen Wendepunkt. Etablierte Systeme wie **CollectiveAccess** haben über Jahrzehnte bewiesen, dass ein flexibles Metadatenschema (*Configuration over Coding*) der richtige Ansatz ist. Dennoch leiden diese Systeme unter massiver Legacy-Last:

- Monolithische PHP-Architektur, schwer wartbar und erweiterbar
- Komplexe XML-Konfigurationen mit hoher Einstiegshürde
- Schlechte API – keine moderne Frontend-Integration möglich
- Keine native Python/Datenscience-Integration

**Katalon** überführt die Flexibilität in Python + React: dynamische Schemata, kontrollierte Vokabulare, Entitätsrelationen – aber mit einer sauberen REST-API, zwei React-Frontends und einer modernen Deployment-Infrastruktur.

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
| Storage | Local (Docker Volumes) |
| Admin-UI | React + TypeScript (Vite) |
| Public-Portal | React + TypeScript (Vite) |
| Deployment | Docker Compose |

---

## 5. Primärtypen

Katalon kennt vier gleichwertige Primärtypen. Alle haben **frei konfigurierbare Metadaten** (Schema-Engine gilt für alle Typen).

| Typ | Beschreibung | Beispiele |
|---|---|---|
| **Object** | Physische oder digitale Artefakte | Fotografie, Dokument, Gemälde |
| **Entity** | Personen oder Organisationen | Fotograf, Verlag, Institution |
| **Place** | Geografische Orte | Stadtbezirk, Gebäude, Region |
| **Occurrence** | Werke, Ereignisse, abstrakte Konzepte (FRBR) | Musikwerk, Ausstellung, Publikation |

Typ-Hierarchien (Untertypen mit eigenen Pflichtfeldern) sind **Post-MVP**.

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

## 11. Nicht im Scope

- Video/Audio-Transcoding
- Leihverkehr / Standortverwaltung
- Typ-Hierarchien (Post-MVP)
- Sets (Nice-to-have, Post-MVP)
