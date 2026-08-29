# OAI-PMH: Export-Mappings und Metadatenformate

## Architektur: wie das aktuell funktioniert

Der Export-Stack besteht aus fuenf Schichten:

| Datei | Verantwortung |
|---|---|
| `backend/src/katalon/api/v1/oai.py` | HTTP-Handler, verb-Dispatch, ES-Query, Format-Gating |
| `backend/src/katalon/api/v1/export.py` | Daten-Dumps (CSV/JSON/XML) fuer den Admin-Export-Bereich |
| `backend/src/katalon/services/oaipmh_service.py` | OAI-PMH-Umschlag (Header, Resumption-Token, Fehler) |
| `backend/src/katalon/integrations/*_format.py` | Format-Plugins (`MetadataFormat`-Subklassen): rendern einen Treffer zu XML |
| `backend/src/katalon/services/metadata_format_service.py` | Registry: laedt Builtins + DB-Overrides/Custom-Adapter |
| `backend/src/katalon/services/metadata_mapping_service.py` | Formatneutrale Feld-zu-Zielpfad-Mappings aus der DB lesen |

Ein Treffer aus Elasticsearch hat diese Struktur (vereinfacht):

```json
{
  "_id": "<uuid>",
  "_source": {
    "record_type": "object",
    "title": "Straße in Marrakesch",
    "status": "public",
    "idno": "INV-1234",
    "metadata": { "photographer": "Mayer", "keywords": ["Reise"] },
    "updated_at": "2026-05-01T12:00:00"
  }
}
```

Ein Format wird nur ausgeliefert, wenn fuer den angefragten Record-Typ mindestens ein Feld darauf gemappt ist (siehe [10_export_mappings.md](./10_export_mappings.md)). Es gibt keinen Rate-Fallback mehr fuer ungemappte Formate/Typen.

## Neues Format hinzufügen — Schritt für Schritt

### Schritt 1: Plugin-Klasse schreiben

Neue Datei unter `backend/src/katalon/integrations/`, z. B. `marc21xml_format.py`:

```python
from __future__ import annotations
import xml.etree.ElementTree as ET
from typing import Any

from katalon.integrations.metadata_format import MetadataFormat, append_path
from katalon.services.metadata_mapping_service import extract_values

class Marc21XmlFormat(MetadataFormat):
    key = "marc21xml"
    label = "MARC21XML"
    targets = {
        "marc:datafield[245]/marc:subfield[a]",  # Titel
        "marc:datafield[100]/marc:subfield[a]",  # Hauptverfasser
    }
    schema_url = "https://www.loc.gov/standards/marcxml/schema/MARC21slim.xsd"
    namespace = "http://www.loc.gov/MARC21/slim"

    def render(self, hit: dict[str, Any], mappings: dict[str, list[str]]) -> ET.Element:
        root = ET.Element("record", {"xmlns": self.namespace})
        for field_name, target_paths in mappings.items():
            for value in extract_values(hit["_source"], field_name):
                for target_path in target_paths:
                    if target_path in self.targets:
                        append_path(root, target_path, value)
        return root
```

`append_path()` aus `metadata_format.py` baut die verschachtelte Elementkette aus einem `/`-getrennten `target_path` — wiederverwendbar fuer jedes hierarchische XML-Format, nicht nur MODS/LIDO.

### Schritt 2: In der Registry bekannt machen

Keine Aenderung an `metadata_format_service.py` noetig — nur eine Zeile in `metadata_formats`:

```sql
INSERT INTO metadata_formats (id, label, adapter_class, config)
VALUES ('marc21xml', 'MARC21XML', 'katalon.integrations.marc21xml_format.Marc21XmlFormat', '{}');
```

`_load_registry()` erkennt den neuen Key, importiert `adapter_class` dynamisch (`importlib`) und instanziiert sie. Ist der Key bereits ein Builtin (`oai_dc`/`lido`/`mets_mods`), wird stattdessen `config` per `setattr` auf die bestehende Instanz gepatcht (z. B. um `targets` zu erweitern), ohne die Klasse zu ersetzen.

**Cache-Hinweis:** Die Registry wird pro Prozess einmal geladen (`_cache`). Nach einem `INSERT`/`UPDATE` auf `metadata_formats` muss der `api`-Container neu gestartet werden, damit die Aenderung wirkt — es gibt aktuell keinen Endpoint, der `metadata_format_service.invalidate_cache()` analog zu `authority_service.invalidate_cache()` (siehe `authority.py`) triggert.

### Schritt 3: Feld-Mappings pflegen

Im Admin-Export-Bereich (Tab „Format-Mapping") erscheint das neue Format automatisch als Spalte (`GET /v1/metadata-mappings/formats` liest die Registry). Zielpfade fuer die Dropdown-Optionen kommen aus `targets` der Klasse.

### Schritt 4: Nichts weiter

`oai.py`, `oaipmh_service.py` und `export.py` brauchen keine Aenderung — Prefix-Validierung, `ListMetadataFormats`, ES-Typ-Filterung und Dump-Rendering laufen generisch ueber die Registry und `mapped_record_types()`/`mapped_format_keys()`.

---

## Aufwandsabschätzung: LIDO-Vollausbau

Der aktuelle `LidoFormat` deckt eine pragmatische Teilmenge ab (Titel, Objekttyp, Beschreibung, ein Ereignisdatum, ein Akteur, Rechte). Fuer einen vollstaendigeren LIDO-Export bleiben bekannte Luecken:

**Ereignis-Struktur mit Rollen (`lido:roleActor`):**
Das ES-Dokument liefert Akteure nur als flache Werte aus dem gemappten Feld, keine Rollen (Fotograf vs. Auftraggeber vs. Vorbesitzer). Ein korrektes Rollen-Mapping braucht einen Zugriff auf die `relations`-Tabelle, die im OAI-/Export-Lesepfad (nur ES) nicht verfuegbar ist.

**`lido:objectWorkType`:**
LIDO erwartet einen kontrollierten Vokabular-Eintrag (SKOS/AAT). Der grobe `record_type` (`object`/`entity`/`place`) reicht dafuer nicht; der eigentliche Objekttyp liegt im Vokabular-Feld des Schemas und muss explizit dorthin gemappt werden.

**Nur fuer Objects sinnvoll:**
LIDO ist auf materielle Objekte ausgelegt. Fuer Entities/Places/Occurrences liefert `mapped_record_types()` ohnehin nur Typen mit tatsaechlichem Mapping — ein Museum mappt LIDO typischerweise nur fuer `object`.

Aufwand fuer Rollen-Ereignisse: zusaetzliche DB-Abfrage im Export-/OAI-Handler, kein reiner Renderer-Umbau.

---

## Warum `/oai` statt `/v1/oai`?

OAI-PMH ist ein Protokoll-Endpunkt, kein versionierter REST-Endpoint. Darum haengt Katalon den OAI-Router direkt unter `/oai` ein.

Harvester sollten immer die kurze URL verwenden:

```text
https://example.org/oai
```

Die uebrige REST API bleibt unter `/v1`, Daten-Dumps liegen unter `/v1/export`.
