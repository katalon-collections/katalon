# Katalon - Export-Mappings

## Worum es geht

Katalon exportiert Metadaten nicht nur ueber OAI-PMH, sondern auch als direkte Daten-Dumps (CSV/JSON) und als XML in mehreren Formaten (OAI-DC, LIDO, METS/MODS). Die Kernidee ist bewusst generisch:

- Ein Feld aus `field_definitions` kann auf mehrere Exportziele gemappt werden.
- Ein Exportziel ist nicht direkt ein Formatname allein, sondern ein konkreter Zielpfad innerhalb eines Formats.
- Format-spezifische Sonderlogik bleibt im Format-Plugin, das Mapping selbst bleibt datengetrieben.
- Ein Format wird nur ausgeliefert (Export-Screen wie OAI-PMH), wenn dafuer tatsaechlich mindestens ein Feld gemappt ist.

## Datenmodell

### `metadata_mappings` — Feld-zu-Zielpfad

```sql
metadata_mappings (
    id UUID,
    field_definition_id UUID,
    format_key VARCHAR,
    target_path VARCHAR,
    settings JSONB,
    sort_order INT,
    is_enabled BOOLEAN,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
)
```

- `field_definition_id`: welches Schemafeld exportiert wird
- `format_key`: z. B. `oai_dc`, `lido`, `mets_mods`
- `target_path`: der konkrete Zielpfad, z. B. `dc:title` oder `mods:titleInfo/mods:title`
- `is_enabled`: Mapping pro Instanz oder Feld deaktivierbar

Ein Feld kann mehrere Mappings haben, auch fuer dasselbe Format, solange die Zielpfade unterschiedlich sind.

### `metadata_formats` — Format-Registry (Plugin-Pattern)

```sql
metadata_formats (
    id VARCHAR PRIMARY KEY,
    label VARCHAR,
    adapter_class VARCHAR,
    config JSONB
)
```

Analog zu `authority_sources`: eine Zeile mit dem Key eines eingebauten Formats (`oai_dc`/`lido`/`mets_mods`) patcht dessen `config` (z. B. eine erweiterte `targets`-Liste) auf die bestehende Instanz. Eine Zeile mit neuem Key laedt `adapter_class` dynamisch (`module.ClassName`) — ein neues Format braucht also keine Aenderung an Registry-Code, nur eine neue Python-Klasse plus diese eine Zeile.

Kein `is_enabled`: Praesenz einer Zeile bedeutet aktiv/override; Formate ganz abschalten ist kein Use-Case, den die UI aktuell braucht.

**Bekannte Einschraenkung:** Die Registry cached pro Prozess (`metadata_format_service._load_registry`). Nach einem `INSERT`/`UPDATE` auf `metadata_formats` braucht es aktuell einen Neustart des `api`-Containers, damit die Aenderung greift — anders als bei Authority-Quellen gibt es noch keinen Endpoint, der `invalidate_cache()` aufruft.

## Formate

### `oai_dc` (`backend/src/katalon/integrations/oai_dc_format.py`)

Die 15 Dublin-Core-Elemente (`dc:title` … `dc:rights`). `dc:type` und `dc:identifier` werden immer strukturell ergaenzt (Record-Typ bzw. OAI-Identifier), unabhaengig vom Mapping — das ist keine Ratelogik, sondern abgeleitete Struktur.

Es gibt **keinen** Fallback mehr fuer ungemappte Felder. Ohne mindestens ein Mapping fuer einen Record-Typ wird `oai_dc` fuer diesen Typ weder in `ListMetadataFormats` angeboten noch ueber `GetRecord`/`ListRecords` ausgeliefert.

### `lido` (`backend/src/katalon/integrations/lido_format.py`)

Pragmatische Teilmenge von LIDO 1.1 (Titel, Objekttyp, Beschreibung, Ereignisdatum, Akteur, Rechte). Produktiv, kein Stub mehr.

### `mets_mods` (`backend/src/katalon/integrations/mets_mods_format.py`)

Pragmatische Teilmenge von MODS 3.x (Titel, Name, Typ, Entstehungsdatum, Abstract, Zugriffsbedingung, Identifier, Sprache). Produktiv, kein Stub mehr.

### Weitere Formate

Siehe [05_oai_serialisierungen.md](./05_oai_serialisierungen.md) fuer die Schritt-fuer-Schritt-Anleitung (neue Klasse + `metadata_formats`-Zeile).

## UI-Verhalten

Die Mapping-Konfiguration sitzt **nicht** mehr im Schema-Editor, sondern im eigenen Export-Bereich (`frontend/admin/src/components/screens/ScreenExport.tsx`, Tab „Format-Mapping"): eine Tabelle Felder × Formate statt einer Konfiguration pro Feld einzeln. Der Export-Bereich hat zusaetzlich einen Tab „Dumps" fuer CSV-/JSON-Downloads je Bestandstyp, unabhaengig vom Format-Mapping.

Container-/Gruppenfelder werden weiterhin nicht direkt gemappt, nur ihre Subfelder.

## Serverseitige Verarbeitung

1. `metadata_format_service.get_format(format_key)` laedt das Plugin (Builtin oder DB-Override/Custom).
2. `metadata_mapping_service.get_mapping_index()` laedt die aktiven Feld-Mappings fuer den Format-Schluessel.
3. `MetadataFormat.render(hit, mappings)` baut daraus das Ziel-XML-Element.

Mapping, Plugin-Auswahl und XML-Struktur sind sauber getrennt: ein neues Format braucht eine neue Klasse plus eine DB-Zeile, keine Aenderung an `oaipmh_service.py`, `oai.py` oder `export.py`.

## Werttransformation

- String-Werte werden als Text exportiert.
- Wiederholbare Felder erzeugen mehrere Ziel-Elemente.
- Dictionaries werden ueber ihren `value`- oder `label`-Inhalt aufgeloest (`metadata_mapping_service.extract_values`/`_flatten_value`).

`settings` auf `metadata_mappings` ist weiterhin frei gehalten fuer spaetere Transformationen (Rollenfilter, Sprachfilter), wird aktuell aber von keinem Format ausgewertet.
