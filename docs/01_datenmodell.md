# Katalon – Datenmodell

## Überblick

Katalon speichert alle Inhalte als eine von vier gleichrangigen Entitätstypen: Objekt, Entität, Ort, Occurrence. Jeder Typ hat eine eigene Datenbanktabelle mit festen Systemfeldern und einem frei konfigurierbaren Metadaten-JSONB-Feld. Die Struktur dieses Metadatenfeldes wird durch das Schema (Felddefinitionen) bestimmt.

---

## Die vier Primärtypen

### Object

Repräsentiert physische oder digitale Artefakte – Dinge, die eine Sammlung verwahrt oder beschreibt.

| Systemfelder | Bedeutung |
|---|---|
| `id` | Interne UUID |
| `idno` | Inventarnummer (eindeutig, Pflicht) |
| `status` | `draft` / `internal` / `public` |
| `metadata` | Alle konfigurierten Felder als JSONB |

**Beispiele aus dem GLAM-Bereich:**
- Glasplattennegativ, Fotografie, Aquarell, Stich
- Handschrift, Urkunde, Brief
- Objekt aus einer Naturkundesammlung (Herbarpresse, Präparat)
- Digitalisat (PDF, Scan, 3D-Modell)

Ein Object kann beliebig viele Mediendateien haben (Bilder, PDFs). Für Bilder wird ein IIIF-Manifest generiert.

### Entity

Repräsentiert Personen und Organisationen, die mit anderen Datensätzen in Beziehung stehen.

| Systemfelder | Bedeutung |
|---|---|
| `id` | Interne UUID |
| `idno` | Eindeutige Kennung (Pflicht) |
| `entity_type` | Subtyp, z.B. `person`, `organisation` |
| `status` | `draft` / `internal` / `public` |
| `metadata` | Alle konfigurierten Felder als JSONB |

**Beispiele:**
- Fotografin (Person) mit GND-Normdateneintrag
- Verlag (Organisation) als Herausgeber
- Behörde als Absender eines Dokuments
- Künstlerkollektiv

### Place

Repräsentiert geografische Orte, optional mit Koordinaten (PostGIS-Geometrie).

| Systemfelder | Bedeutung |
|---|---|
| `id` | Interne UUID |
| `idno` | Eindeutige Kennung (Pflicht) |
| `geom` | PostGIS-Punkt (WGS84, optional) |
| `status` | `draft` / `internal` / `public` |
| `metadata` | Alle konfigurierten Felder als JSONB |

**Beispiele:**
- Aufnahmeort einer Fotografie (Straße, Stadtteil, Gebäude)
- Herkunftsort eines Objekts
- Produktionsstätte
- Administrative Einheit (Gemeinde, Bezirk)

### Occurrence

Repräsentiert Werke, Ereignisse und abstrakte Konzepte – Dinge ohne physischen Träger (angelehnt an FRBR).

| Systemfelder | Bedeutung |
|---|---|
| `id` | Interne UUID |
| `idno` | Eindeutige Kennung (Pflicht) |
| `occurrence_type` | Subtyp, z.B. `work`, `event`, `concept` |
| `status` | `draft` / `internal` / `public` |
| `metadata` | Alle konfigurierten Felder als JSONB |

**Beispiele:**
- Musikwerk (als abstraktes Werk, unabhängig von physischen Noten oder Aufnahmen)
- Ausstellung (Ereignis) mit Datum und Ort
- Ikongrafisches Motiv als Konzept
- Publikation (bibliografisches Werk)

---

## Dynamisches Schema (Felddefinitionen)

Jeder Primärtyp hat ein konfigurierbares Schema aus Felddefinitionen (`field_definitions`). Admins legen diese Felder über die Admin-UI an – ohne Datenbankmigrationen.

### Struktur einer Felddefinition

```sql
field_definitions (
    id            UUID,
    target_type   VARCHAR,   -- object / entity / place / occurrence
    target_subtype VARCHAR,  -- optional: nur für einen Subtyp gültig
    name          VARCHAR,   -- interner Bezeichner, z.B. "photographer"
    label         JSONB,     -- {"de": "Fotograf:in", "en": "Photographer"}
    field_type    VARCHAR,   -- siehe Feldtypen unten
    is_required   BOOLEAN,
    is_repeatable BOOLEAN,
    sort_order    INT,
    settings      JSONB      -- feldtyp-spezifische Optionen
)
```

### Feldtypen

| Feldtyp | Beschreibung | Beispiel |
|---|---|---|
| `text` | Einzeiliger Freitext, optional mit Regex-Validierung | Titel, ISBN, Signatur |
| `richtext` | Mehrzeiliger Text mit Formatierung (HTML) | Beschreibungstext, Provenienz |
| `date` | Datum nach EDTF (auch unscharfe Angaben wie „um 1920") | Entstehungsdatum, Erwerbsdatum |
| `number` | Numerischer Wert | Höhe in cm, Gewicht, Auflage |
| `boolean` | Ja/Nein-Wert | Ist restauriert?, Ist digitalisiert? |
| `vocab` | Auswahl aus einem kontrollierten Vokabular | Materialart, Genre, Kameratyp |
| `relation` | Verknüpfung zu einem anderen Datensatz (Object, Entity, Place, Occurrence) | Fotograf (→ Entity), Aufnahmeort (→ Place) |
| `geo` | Geografische Koordinaten (Punkt) | Fundort, Aufnahmestandort |
| `pid` | Persistenter Identifier mit Normdatenverknüpfung (GND, VIAF, Geonames …) | GND-ID einer Person, Geonames-ID |

### Wiederholbare Felder

Jedes Feld kann als `is_repeatable: true` definiert werden. Dann können mehrere Werte pro Datensatz gespeichert werden.

Einfaches (nicht wiederholbares) Feld in JSONB:
```json
{"title": "Straße in Marrakesch"}
```

Wiederholbares Feld in JSONB:
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

## Subtypes (Untertypen)

Entity und Occurrence haben ein Subtyp-Feld (`entity_type` bzw. `occurrence_type`). Subtypen sind frei gewählte Zeichenketten — es gibt keine vordefinierte Liste.

**Typische Subtypen:**

| Primärtyp | Subtypen (Beispiele) |
|---|---|
| Entity | `person`, `organisation`, `koerperschaft` |
| Occurrence | `work`, `event`, `concept`, `publication` |

Felddefinitionen können subtyp-spezifisch sein: Ein Feld mit `target_subtype = "person"` erscheint nur bei Entitäten vom Subtyp `person`, nicht bei Organisationen. Felder ohne `target_subtype` gelten für alle Subtypen des jeweiligen Primärtyps.

---

## Relationen

Alle vier Primärtypen können miteinander verknüpft werden. Relationen sind gerichtet (von → zu) und tragen einen Relationstyp sowie optional freie Metadaten.

```sql
relations (
    id            UUID,
    from_type     VARCHAR,   -- object / entity / place / occurrence
    from_id       UUID,
    to_type       VARCHAR,
    to_id         UUID,
    relation_type VARCHAR,   -- z.B. "hat_fotografiert", "ist_aufgenommen_in"
    metadata      JSONB,     -- z.B. {"role": "Auftraggeber", "date_range": "1923–1930"}
    created_at    TIMESTAMPTZ
)
```

**Beispiele:**
- Object → Entity: `hat_fotografiert` (mit optionalem Rollenfeld in `metadata`)
- Object → Place: `ist_aufgenommen_in`
- Object → Occurrence: `ist_exemplar_von` (z.B. Druck eines Werks)
- Entity → Entity: `ist_mitglied_von` (Person → Organisation)
- Occurrence → Place: `hat_stattgefunden_in` (Ereignis → Ort)

Der Relationstyp ist eine freie Zeichenkette. Empfehlung: Werte aus einem Vokabular verwenden, um Konsistenz zu gewährleisten.

---

## Vokabulare

Vokabulare sind kontrollierte Termlisten, die für `vocab`-Felder verwendet werden. Sie können hierarchisch aufgebaut sein (Eltern-Kind-Beziehung zwischen Termen).

```sql
vocabularies (
    id              UUID,
    name            VARCHAR,       -- z.B. "Materialarten"
    is_hierarchical BOOLEAN
)

vocabulary_terms (
    id              UUID,
    vocabulary_id   UUID,
    term            VARCHAR,       -- interner Bezeichner
    label           JSONB,         -- {"de": "Silbergelatine", "en": "Silver gelatin"}
    parent_id       UUID           -- NULL = Wurzelelement
)
```

**Wann braucht man Vokabulare?**

Immer dann, wenn ein Feld nur bestimmte, vorab definierte Werte annehmen soll — und nicht Freitext. Typische Anwendungsfälle:

- Materialgattungen (Silbergelatine, Albumin, Zyanotypie …)
- Kameratypen
- Genres, Gattungen
- Rollen in Relationen (Auftraggeber, Techniker, Verleger …)
- Medientypen (Vorderseite, Rückseite, Detail …)

Terme können hierarchisch verschachtelt werden. Ein Vokabular „Technik" könnte z.B. so aussehen:

```
Fotografie
├── Nassplatte
├── Trockenplatte
│   ├── Silbergelatine
│   └── Kollodium-Trockenplatte
└── Direktpositiv
```

---

## Snapshots (Versionierung)

Snapshots speichern einen benannten Zustand eines Datensatzes. Sie werden manuell angelegt und ermöglichen es, zu einem früheren Stand zurückzublicken oder Abgabestände zu dokumentieren.

```sql
record_snapshots (
    id          UUID,
    record_type VARCHAR,    -- object / entity / place / occurrence
    record_id   UUID,
    label       VARCHAR,    -- z.B. "Abgabe ans Museum 2024-03"
    snapshot    JSONB,      -- vollständiger Datensatz-Zustand zum Zeitpunkt
    created_by  UUID,
    created_at  TIMESTAMPTZ
)
```

Snapshots sind unveränderlich. Sie ersetzen keine vollständige Versionskontrolle, sind aber als Meilenstein-Dokumentation geeignet.

---

## Audit Log

Das Audit Log zeichnet automatisch jede Änderung an einem Datensatz auf.

```sql
audit_log (
    id             UUID,
    record_type    VARCHAR,    -- object / entity / place / occurrence
    record_id      UUID,
    user_id        UUID,
    action         VARCHAR,    -- create / update / delete
    changed_fields JSONB,      -- {"title": ["alter Wert", "neuer Wert"]}
    created_at     TIMESTAMPTZ
)
```

Jedes Create, Update und Delete wird protokolliert — mit Benutzer-ID, Zeitstempel und den geänderten Feldern (Vorher/Nachher). Das Audit Log kann nicht manuell editiert werden.
