# Katalon Collections

>This project is 100% AI-generated. Every line of code, every architectural decision's implementation, and every commit was written by AI. The human developer serves solely as the decision-maker and product manager — defining what to build, not how to build it.

Turn-key Open-Source Metadata Management System (MMS) für den GLAM-Sektor — Galerien, Bibliotheken, Archive, Museen.

*Katalon Collections* (kurz "Katalon" im Code und in der Entwicklungsdokumentation) ist eigenständig und nicht mit [katalon.com](https://katalon.com/) (Test-Automatisierung) verbunden.

Katalon verbindet flexible, dynamische Metadatenschemata mit einer sauberen REST-API, zwei spezialisierten Frontends und einer containerisierten Deployment-Infrastruktur.

---

## Was ist Katalon?

Sammlungsverantwortliche stehen vor der Herausforderung, heterogene Bestände mit individuellen Metadatenfeldern zu erfassen, zu verknüpfen und der Öffentlichkeit zugänglich zu machen. Katalon setzt dabei auf *Configuration over Coding*: Schemata werden konfiguriert statt programmiert.

Katalon baut auf einem modernen Stack:

- **Dynamische Schemata** — Jedes Feld pro Typ konfigurierbar, wiederholbar, mehrsprachig
- **Kontrollierte Vokabulare** — Hierarchische Begriffssysteme mit Import aus CSV/JSON
- **Typisierte Relationen** — Fachlich benannte Formularfelder und freie Zusatzbeziehungen im gemeinsamen Beziehungsgraphen
- **IIIF als first-class citizen** — Hochauflösender Deep-Zoom für Digitalisate
- **Volltextsuche**
- **Facettierte Suche über alle Bestände**
- **Theme-System** — Public-Portal per Drop-in-Bundle anpassbar, kein Rebuild nötig

Unique Selling Points:

- Extrem konfortabler Datenimport (WYSIWYG Mapping inkl. Transformationen)
- Skalierbare Architektur
- Exporter GUI (Eigenes Datenmodell auf Schema mappen)
- KI-assistierte Felder
- Extrem einfache Installtion dank Docker Compose

---

## Prinzipien

1. **Datenintegrität und Sicherheit von Metadaten und Medien**
2. **User Experience: Simplizität und Flexibilität.** Kuratorinnen und Sachbearbeiter konfigurieren Schemata über die Oberfläche, nicht über Config-Dateien oder Code. Die Software passt sich an die Sammlung an und nicht umgekehrt.
3. **Techstack.** Moderne, etablierte und gut gewartete Technologien. Performance und Angriffsresistenz. Eine Portalansicht kommt direkt mit. Mit überschaubarem Aufwand zu Installieren und Betreiben.
4. **Kostenlos, einfach anpassbar, Import selbst machbar.** Katalon ist Open Source, keine Lizenzkosten. Institutionen mit kleinem Budget importieren ihre Bestände selbst (Smart Importer, Dry-Run-Vorschau) statt einen Dienstleister zu beauftragen.
5. **Kein Lock-in.** REST-API mit OpenAPI-Spec, OAI-PMH, ein dokumentiertes, einfaches Datenmodell. Institutionen nehmen ihre Daten jederzeit mit.
6. **Standardkonformität.** Anschluss an GLAM-Standards (IIIF, Dublin Core, ggf. LIDO/EAD) statt proprietärer Formate. Nutzung von Normdaten.
7. **Barrierefreiheit.** Das öffentliche Portal ist für alle nutzbar.
8. **Anpassbar.** Falls doch eine Speziallösung oder ein eigenes Portal genutzt werden soll.

---

## Schnellstart

```bash
# Repository klonen
git clone https://github.com/karkraeg/Katalon.git
cd Katalon
./install.sh --up
```

**Voraussetzungen:** Docker + Docker Compose v2

### Erster Login

Beim ersten Start generiert Katalon automatisch ein sicheres Admin-Passwort. `install.sh` zeigt die Zugangsdaten direkt nach dem Start an und kopiert sie nach `./first-run-credentials.txt`.

Wer den Stack ohne `install.sh` startet (z. B. `docker compose up -d`), findet die Zugangsdaten:

```bash
# im API-Container
docker compose exec api cat /var/lib/katalon/first-run-credentials.txt

# oder in den Logs (einmalig beim ersten Start)
docker compose logs api | grep -A5 "KATALON FIRST RUN"
```

> **Ohne gesetztes `KATALON_BASE_URL`** (z. B. lokale Entwicklung) wird statt eines generierten Passworts der Wert `DEFAULT_ADMIN_PASSWORD` aus der `.env` verwendet (Standard: `admin`).

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

### Beziehungen und verknüpfte Suche

Fachlich benannte Beziehungen wie „Autor:in“ oder „Aufnahmeort“ werden als
Relationsfelder im Schema konfiguriert. Sie können einen Zieltyp, ein
Relationstyp-Vokabular und optional einen festen Relationstyp festlegen.
Die Beziehungen-Karte zeigt den vollständigen Graphen und erfasst nur weitere,
freie Beziehungen zu anderen Haupttypen.

Ausgewählte Felder verknüpfter Records können in Elasticsearch eingebettet und
im Portal als Facetten aktiviert werden. Ein festgelegter Relationstyp begrenzt
die Suche auf diese fachliche Beziehung; ohne ihn werden alle Beziehungen zum
gewählten Zieltyp berücksichtigt.

### Vokabulare

Hierarchische kontrollierte Begriffssysteme — importierbar aus CSV, TSV oder JSON. Unterstützt Übersetzungen, Oberbegriffe und externe IDs (z. B. GND).

### Normdaten-Integration

Integrierte Adapter für GND, GeoNames, VIAF, Wikidata, Getty TGN und ICONCLASS. Normdaten-Einträge können direkt in Erfassungsformularen gesucht und verknüpft werden.

### OAI-PMH

Standardschnittstelle für Metadaten-Harvesting mit generischer Export-Mapping-Schicht. OAI-PMH nutzt aktuell `oai_dc`, spaeter koennen weitere Formate wie LIDO oder METS/MODS an dieselbe Infrastruktur angeschlossen werden.

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

OpenAPI-Dokumentation: `http://localhost:8000/api/docs`

Wichtige Endpunkte:

| Methode        | Pfad                           | Beschreibung                                               |
|----------------|--------------------------------|------------------------------------------------------------|
| POST           | `/v1/auth/token`               | JWT-Login                                                  |
| GET            | `/v1/objects`                  | Objekte auflisten (Pagination, Filter)                     |
| POST           | `/v1/objects`                  | Neues Objekt anlegen                                       |
| GET/PUT/DELETE | `/v1/objects/{id}`             | Objekt lesen/aktualisieren/löschen                         |
| GET            | `/v1/schema/{target_type}`     | Felddefinitionen abrufen                                   |
| GET/POST       | `/v1/schema/import`            | Schema aus YAML/JSON importieren                           |
| GET            | `/v1/vocabularies`             | Vokabulare auflisten                                       |
| POST           | `/v1/vocabularies/{id}/import` | Vokabular-Terme aus CSV/JSON importieren (Dry-Run/Replace) |
| GET            | `/v1/search`                   | Volltext- und Facettensuche                                |
| POST           | `/v1/pids/mint`                | ARK oder DNB-URN über den PID-Feldanbieter vergeben         |
| GET            | `/v1/authorities/search`       | Normdaten-Suche                                            |
| GET            | `/oai`                         | OAI-PMH Endpoint                                           |
| GET            | `/v1/portal/config`            | Portal-Konfiguration                                       |
| POST           | `/v1/portal/logo`              | Logo hochladen                                             |
| GET            | `/v1/audit`                    | Audit-Log abrufen                                          |

### Persistente Identifier (PID)

- PID-Felder verwenden ARK oder DNB-URN; sie sind erst in der Schema-Verwaltung auswählbar, wenn ihr Dienst vollständig konfiguriert ist.
- ARKs brauchen einen registrierten produktiven NAAN und eine dauerhafte `KATALON_BASE_URL`; die Instanz löst sie unter `/ark:/<NAAN>/<Suffix>` auf.
- Für lokale DNB-URN-Entwicklung kann der Mock-Endpunkt genutzt werden: `DNB_URN_API_URL=http://localhost:8000/v1/dnb-urn-mock`.

## Admin-UI

- **Objekte / Entitäten / Orte / Occurrences** — Tabellenansicht + dynamisches Erfassungsformular
- **Schemata** — Feldkonfiguration pro Typ, YAML/JSON-Import
- **Metadaten-Export** — Felddefinitionen auf Exportformate mappen
- **Vokabular** — Kontrollierte Listen verwalten
- **Importer** — CSV/Excel-Import-Wizard mit Dry-Run
- **Statische Seiten** — Portal-Inhaltsseiten
- **Benutzer** — Rollenbasierte Benutzerverwaltung
- **Einstellungen** — Portal-Konfiguration, Logo, Farben
- **Audit-Log** — Vollständige Änderungshistorie

---

## Dokumentation

Die Anwender- und Betriebsdokumentation liegt im separaten Docs-Repo:

```text
https://github.com/karkraeg/katalon-docs
```

Die lokale `docs/`-Ablage bleibt vorerst als Übergangskopie im Hauptrepo.

---

## Entwicklung

Für lokale Entwicklung ohne Docker siehe [`.agents/DEV.md`](.agents/DEV.md).

---

## Lizenz

[AGPL-3.0-or-later](LICENSE)
