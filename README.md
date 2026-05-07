# Katalon

Open-Source Metadata Management System (MMS) für den GLAM-Sektor — Galerien, Bibliotheken, Archive, Museen.

Katalon ist ein moderner Python/React-Rewrite der Kernfunktionalitäten von [CollectiveAccess](https://collectiveaccess.org). Es vereint die bewährte Flexibilität dynamischer Metadatenschemata mit einer sauberen REST-API, zwei spezialisierten Frontends und einer containerisierten Deployment-Infrastruktur.

---

## Was ist Katalon?

Sammlungsverantwortliche stehen vor der Herausforderung, heterogene Bestände mit individuellen Metadatenfeldern zu erfassen, zu verknüpfen und der Öffentlichkeit zugänglich zu machen. Etablierte Systeme wie CollectiveAccess haben bewiesen, dass *Configuration over Coding* der richtige Ansatz ist — leiden aber unter monolithischer Legacy-Architektur, komplexer XML-Konfiguration und fehlender API für moderne Frontends.

Katalon überführt diese Flexibilität in eine moderne Stack:

- **Dynamische Schemata** — Jedes Feld pro Typ konfigurierbar, wiederholbar, mehrsprachig
- **Kontrollierte Vokabulare** — Hierarchische Begriffssysteme mit Import aus CSV/JSON
- **Entitätsrelationen** — Beliebige Verknüpfungen zwischen Objekten, Personen, Orten und Werken
- **IIIF als first-class citizen** — Hochauflösender Deep-Zoom für Digitalisate
- **Volltextsuche**
- **Facettierte Suche über alle Bestände**
- **Theme-System** — Public-Portal per Drop-in-Bundle anpassbar, kein Rebuild nötig

---

## Schnellstart

```bash
# Repository klonen
git clone https://github.com/karkraeg/Katalon.git
cd Katalon
./install.sh --up
```

**Voraussetzungen:** Docker + Docker Compose v2

---

## Architektur

```text
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

**Stack:** FastAPI · PostgreSQL 16 + PostGIS · Elasticsearch 8 · Redis · Celery · Cantaloupe (IIIF) · React 18 + TypeScript

---

## Kernfunktionen

### Vier Primärtypen

| Typ            | Beschreibung                          | Beispiele                           |
|----------------|---------------------------------------|-------------------------------------|
| **Object**     | Physische oder digitale Artefakte     | Fotografie, Dokument, Gemälde       |
| **Entity**     | Personen oder Organisationen          | Fotograf, Verlag, Institution       |
| **Place**      | Geografische Orte                     | Stadtbezirk, Gebäude, Region        |
| **Occurrence** | Werke, Ereignisse, abstrakte Konzepte | Musikwerk, Ausstellung, Publikation |

Alle Typen haben **frei konfigurierbare Metadatenfelder** — definiert im Admin-UI und dynamisch in der Datenbank gespeichert (JSONB).

### Schema-Engine

Felder pro Typ definierbar mit:

- Feldtyp (Text, Datum, Zahl, Geo, Vokabular, Relation, Boolean)
- Wiederholbarkeit
- Pflichtfeld
- Mehrsprachige Labels
- Feldspezifische Einstellungen

### Vokabulare

Hierarchische kontrollierte Begriffssysteme — importierbar aus CSV, TSV oder JSON. Unterstützt Übersetzungen, Oberbegriffe und externe IDs (z. B. GND).

### Normdaten-Integration

Integrierte Adapter für GND, GeoNames, VIAF, Wikidata, Getty TGN und ICONCLASS. Normdaten-Einträge können direkt in Erfassungsformularen gesucht und verknüpft werden.

### OAI-PMH

Standardschnittstelle für Metadaten-Harvesting mit Dublin-Core-Mapping.

### Theming

Das Public-Portal ist vollständig themebar per **Drop-in Bundle** — kein Rebuild, kein Store:

```bash
# Theme ablegen
cp -r mein-archiv/ /var/lib/katalon/themes/mein-archiv/

# Aktivieren
echo "PORTAL_THEME=mein-archiv" >> .env
docker compose restart portal
```

Ein Theme-Bundle besteht aus `theme.json` (CSS-Tokens, Fonts, Logo) + optionalem `custom.css`.

---

## API

OpenAPI-Dokumentation: `http://localhost:8000/docs`

Wichtige Endpunkte:

| Methode        | Pfad                           | Beschreibung                           |
|----------------|--------------------------------|----------------------------------------|
| POST           | `/v1/auth/token`               | JWT-Login                              |
| GET            | `/v1/objects`                  | Objekte auflisten (Pagination, Filter) |
| POST           | `/v1/objects`                  | Neues Objekt anlegen                   |
| GET/PUT/DELETE | `/v1/objects/{id}`             | Objekt lesen/aktualisieren/löschen     |
| GET            | `/v1/search`                   | Volltext- und Facettensuche            |
| GET            | `/v1/schema/{target_type}`     | Felddefinitionen abrufen               |
| GET/POST       | `/v1/schema/import`            | Schema aus YAML/JSON importieren       |
| GET            | `/v1/vocabularies`             | Vokabulare auflisten                   |
| POST           | `/v1/vocabularies/{id}/import` | Vokabular-Terme importieren            |
| GET            | `/v1/authorities/search`       | Normdaten-Suche                        |
| GET            | `/v1/oai`                      | OAI-PMH Endpoint                       |

---

## Admin-UI

- **Objekte / Entitäten / Orte / Occurrences** — Tabellenansicht + dynamisches Erfassungsformular
- **Schemata** — Feldkonfiguration pro Typ, YAML/JSON-Import
- **Vokabular** — Kontrollierte Listen verwalten
- **Importer** — CSV/Excel-Import-Wizard mit Dry-Run
- **Statische Seiten** — Portal-Inhaltsseiten
- **Benutzer** — Rollenbasierte Benutzerverwaltung
- **Einstellungen** — Portal-Konfiguration, Logo, Farben
- **Audit-Log** — Vollständige Änderungshistorie

---

## Dokumentation

| Dokument                                                             | Inhalt                                                 |
|----------------------------------------------------------------------|--------------------------------------------------------|
| [`KONZEPT.md`](KONZEPT.md)                                           | Vollständiges Konzept mit Datenmodell und User-Stories |
| [`docs/00_architektur.md`](docs/00_architektur.md)                   | Systemarchitektur, Service-Details, Auth-Flow          |
| [`docs/01_datenmodell.md`](docs/01_datenmodell.md)                   | Datenbankschema, ORM-Modelle                           |
| [`docs/02_schema_verwaltung.md`](docs/02_schema_verwaltung.md)       | Schema-Engine, Feldtypen, Import-Format                |
| [`docs/03_csv_import.md`](docs/03_csv_import.md)                     | Vokabular-Import, CSV-Mapping                          |
| [`docs/04_produktion.md`](docs/04_produktion.md)                     | Produktions-Deployment, TLS, nginx                     |
| [`docs/05_oai_serialisierungen.md`](docs/05_oai_serialisierungen.md) | OAI-PMH Formate und Mappings                           |
| [`docs/06_anpassungen.md`](docs/06_anpassungen.md)                   | Theme-System, Custom CSS                               |

---

## Entwicklung

Für lokale Entwicklung ohne Docker siehe [`.agents/DEV.md`](.agents/DEV.md).


---

## Lizenz

MIT
