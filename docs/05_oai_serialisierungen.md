# OAI-PMH: Export-Mappings und Metadatenformate

## Architektur: wie das aktuell funktioniert

Der OAI-PMH-Stack besteht aus drei Schichten:

| Datei | Verantwortung |
|---|---|
| `backend/src/katalon/api/v1/oai.py` | HTTP-Handler, verb-Dispatch, ES-Query |
| `backend/src/katalon/services/oaipmh_service.py` | XML-Serialisierung (DC-Mapping, verb-Responses) |
| `backend/src/katalon/services/metadata_mapping_service.py` | Formatneutrale Export-Mappings aus der DB lesen |

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
    "updated_at": "2026-05-01T12:00:00",
    "related_entities": ["Max Mustermann"],
    "related_places": ["Marrakesch"]
  }
}
```

 Das aktuelle Format `oai_dc` nutzt die generische Export-Mapping-Schicht aus `metadata_mappings`. Wenn Mappings fuer einen Record-Typ vorhanden sind, werden sie exportiert. Ohne Mappings bleibt ein konservativer Fallback aktiv.

Die generische Architektur ist in [10_export_mappings.md](./10_export_mappings.md) beschrieben.

## Neue Serialisierung hinzufügen — Schritt für Schritt

### Schritt 1: Serializer in `oaipmh_service.py`

Füge eine neue Funktion analog zu `_hit_to_oai_record()` hinzu:

```python
MODS_NS = "http://www.loc.gov/mods/v3"

def _hit_to_mods(hit: dict[str, Any], set_spec: str | None) -> ET.Element:
    src = hit["_source"]
    record_id = hit["_id"]
    md: dict = src.get("metadata", {})

    oai_rec = ET.Element("record")
    header = ET.SubElement(oai_rec, "header")
    ET.SubElement(header, "identifier").text = f"oai:katalon:{src.get('record_type')}:{record_id}"
    ET.SubElement(header, "datestamp").text = _datestamp(src.get("updated_at"))
    if set_spec:
        ET.SubElement(header, "setSpec").text = set_spec

    metadata_el = ET.SubElement(oai_rec, "metadata")
    mods = ET.SubElement(metadata_el, "mods", {
        "xmlns": MODS_NS,
        "version": "3.7",
    })
    title_info = ET.SubElement(mods, "titleInfo")
    ET.SubElement(title_info, "title").text = str(src.get("title") or record_id)

    # ... weiteres Mapping

    return oai_rec
```

### Schritt 2: Format registrieren

Wenn ein neues Format angeboten werden soll, muss es in `ListMetadataFormats` erscheinen und im Handler akzeptiert werden. Die aktuelle Implementierung prueft den Prefix noch direkt im Handler. Fuer neue Formate empfiehlt sich, die Prefix-Validierung und die Serializer-Auswahl zusammenzufassen.

```python
# Typ: MetadataPrefix → Callable(hit, set_spec) → ET.Element
RECORD_SERIALIZERS: dict[str, Callable[[dict, str | None], ET.Element]] = {
    "oai_dc": _hit_to_oai_record,
    "mods":   _hit_to_mods,
    # "lido": _hit_to_lido,
}
```

Dann in `list_records`, `list_identifiers`, `get_record`:

```python
serializer = RECORD_SERIALIZERS.get(prefix)
if serializer is None:
    return _error(root, "cannotDisseminateFormat", f"Unsupported prefix: {prefix}")
# ...
for hit in hits:
    lr.append(serializer(hit, set_spec))
```

### Schritt 3: Format in `ListMetadataFormats` registrieren

```python
METADATA_FORMATS = [
    {
        "prefix": "oai_dc",
        "schema": "http://www.openarchives.org/OAI/2.0/oai_dc.xsd",
        "namespace": "http://www.openarchives.org/OAI/2.0/oai_dc/",
    },
    {
        "prefix": "mods",
        "schema": "http://www.loc.gov/standards/mods/v3/mods-3-7.xsd",
        "namespace": "http://www.loc.gov/mods/v3",
    },
]

def list_metadata_formats(base_url: str) -> str:
    root = _root()
    req = ET.SubElement(root, "request", verb="ListMetadataFormats")
    req.text = base_url
    lmf = ET.SubElement(root, "ListMetadataFormats")
    for fmt in METADATA_FORMATS:
        fmt_el = ET.SubElement(lmf, "metadataFormat")
        ET.SubElement(fmt_el, "metadataPrefix").text = fmt["prefix"]
        ET.SubElement(fmt_el, "schema").text = fmt["schema"]
        ET.SubElement(fmt_el, "metadataNamespace").text = fmt["namespace"]
    return ET.tostring(root, encoding="unicode", xml_declaration=True)
```

### Schritt 4: Prefix-Validierung in `oai.py` vereinheitlichen

Wenn mehr als ein Format aktiv ist, sollte die Prefix-Validierung zentral erfolgen. Das verhindert, dass `ListRecords`, `ListIdentifiers` und `GetRecord` auseinanderlaufen.

---

## Aufwandsabschätzung: LIDO

**LIDO** (Lightweight Information Describing Objects) ist der GLAM-Standard für Objektmetadaten, verwendet von Museen, Archiven und Aggregatoren (Europeana, Deutsche Digitale Bibliothek).

### Was gut passt (aus dem ES-Dokument direkt ableitbar)

| LIDO-Element | Quelle im ES-Dokument | Aufwand |
|---|---|---|
| `lido:lidoRecID` | `_id` + `record_type` | trivial |
| `lido:titleSet/appellationValue` | `title` | trivial |
| `lido:repositorySet` (Inventarnr.) | `idno` | trivial |
| `lido:recordWrap/recordID` | `_id` | trivial |
| `lido:recordWrap/recordType` | `record_type` | trivial |
| `lido:recordMetadataDate` | `updated_at` | trivial |
| `lido:subjectSet` (Schlagwörter) | `metadata.keywords` | gering |
| `lido:rightsWorkSet` | `metadata.rights/license` | gering |
| `lido:resourceSet` (IIIF-Link) | Cantaloupe-URL aus Config | mittel |

### Was Aufwand macht

**Ereignis-Struktur (`lido:eventSet`):**
LIDO beschreibt Herstellung, Erwerb, Verwendung als verschachtelte Events mit Akteuren und Orten. Unser ES-Dokument hat `related_entities` nur als flache String-Liste (Namen), keine Rollen. Ein minimales Mapping (nur "Production"-Event mit Creator) ist machbar, aber ein korrektes Mapping mit Rollen (`lido:roleActor`) bräuchte die Relations-Tabelle — und die ist bei der OAI-Abfrage nicht verfügbar (nur ES-Daten).

**`lido:objectWorkType`:**
LIDO erwartet kontrollierten Vokabular-Eintrag (SKOS, AAT). Unser `record_type` (`object`/`entity`/`place`) ist zu grob; der echte Objekttyp liegt im Vokabular-Feld des Schemas. Mapping ohne Vokabular-Lookup ist nur annähernd korrekt.

**Nur für Objects sinnvoll:**
LIDO ist auf materielle Objekte ausgelegt. Entities, Places und Occurrences lassen sich nicht sauber auf LIDO mappen. Der LIDO-Serializer würde also `record_type != "object"` überspringen oder minimale Felder liefern.

### Aufwand-Einschätzung

| Variante | Aufwand | Ergebnis |
|---|---|---|
| Minimales LIDO (Titel, ID, Rechte, Typ) | 3–4 h | Valides XML, aber dünn |
| LIDO mit eventSet (Creator), resourceSet (IIIF) | 1–1,5 Tage | Praxistauglich für DDB/Europeana |
| LIDO mit Rollen aus Relations-Tabelle | +0,5 Tage | Erfordert zusätzliche DB-Abfrage im OAI-Handler |

Für eine Europeana-Einspielung wäre Variante 2 der Mindeststandard.

### Was dafür zu tun wäre (konkret)

1. `_hit_to_lido(hit, set_spec) -> ET.Element` in `oaipmh_service.py`
2. LIDO-Namespace-Deklarationen (`http://www.lido-schema.org`)
3. `RECORD_SERIALIZERS["lido"] = _hit_to_lido` eintragen
4. `METADATA_FORMATS` um LIDO erweitern
5. Testen gegen den [LIDO-Validator](https://validator.lido-schema.org/)

---

## Könnte die Admin-Oberfläche das steuern?

**Was bereits sinnvoll umgesetzt ist:** Das Mapping selbst wird pro Feld im Schema-Editor konfiguriert, nicht im OAI-Handler.

**Was spaeter ergaenzt werden kann:** Aktivieren/Deaktivieren einzelner Formate je Installation. Beispiel: eine Instanz liefert nur `oai_dc`, eine andere zusaetzlich `lido`.

**Mogliche naechste Ausbaustufe:**
- Neue Tabelle `oai_metadata_formats (prefix VARCHAR PK, is_enabled BOOLEAN)` mit Seed-Daten fuer alle verfuegbaren Formate
- `list_metadata_formats` liest nur aktivierte Formate aus der DB
- `cannotDisseminateFormat`-Check prueft zusaetzlich gegen aktivierte Formate
- Admin-UI: Toggle-Liste in den OAI-Einstellungen

Das ist ~0,5 Tage Backend + ~0,5 Tage Frontend, setzt aber die Registry-Umstrukturierung (Schritte 1–4 oben) voraus.

---

## Warum `/oai` statt `/v1/oai`?

OAI-PMH ist ein Protokoll-Endpunkt, kein versionierter REST-Endpoint. Darum hängt Katalon den OAI-Router direkt unter `/oai` ein.

Harvester sollten immer die kurze URL verwenden:

```text
https://example.org/oai
```

Die übrige REST API bleibt unter `/v1`.
