# OAI-PMH: Neue Metadatenformate hinzufügen

## Architektur: wie das aktuell funktioniert

Der OAI-PMH-Stack besteht aus zwei Dateien:

| Datei | Verantwortung |
|---|---|
| `backend/src/katalon/api/v1/oai.py` | HTTP-Handler, verb-Dispatch, ES-Query |
| `backend/src/katalon/services/oaipmh_service.py` | XML-Serialisierung (DC-Mapping, verb-Responses) |

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

Das aktuelle Format `oai_dc` ist in `_hit_to_oai_record()` implementiert.

## Neue Serialisierung hinzufügen — Schritt für Schritt

### Schritt 1: Mapping-Funktion in `oaipmh_service.py`

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

### Schritt 2: Format-Registry einführen

Ersetze die hartkodierte Prüfung `if prefix != "oai_dc"` durch eine Registry am Anfang von `oaipmh_service.py`:

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

Aktuell steckt `prefix != "oai_dc"` dreimal im Handler (ListRecords, ListIdentifiers, GetRecord). Nach der Registry-Einführung ersetzt ein einziger Import-Check alle drei:

```python
from katalon.services.oaipmh_service import RECORD_SERIALIZERS

if prefix not in RECORD_SERIALIZERS:
    xml = oaipmh_service._error(root, "cannotDisseminateFormat", ...)
    return Response(...)
```

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

**Was sinnvoll wäre:** Aktivieren/Deaktivieren einzelner Formate je Installation. Beispiel: eine Instanz liefert nur `oai_dc`, eine andere zusätzlich `lido`.

**Was nicht sinnvoll wäre:** Das Mapping selbst konfigurieren — das ist Python-Code, nicht konfigurierbare Daten.

**Empfohlene Umsetzung (wenn gewünscht):**
- Neue Tabelle `oai_metadata_formats (prefix VARCHAR PK, is_enabled BOOLEAN)` mit Seed-Daten für alle verfügbaren Formate
- `list_metadata_formats` liest nur aktivierte Formate aus der DB
- `cannotDisseminateFormat`-Check prüft zusätzlich gegen aktivierte Formate
- Admin-UI: einfache Toggle-Liste in den OAI-Einstellungen

Das ist ~0,5 Tage Backend + ~0,5 Tage Frontend, setzt aber die Registry-Umstrukturierung (Schritte 1–4 oben) voraus.

---

## Warum `/v1/oai` statt `/oai`?

Der OAI-Router wird in `main.py` wie alle anderen Router mit `prefix="/v1"` eingehängt. OAI-PMH kennt keine Protokoll-Versionierung, daher ist `/v1` semantisch unpassend — er ist nur ein Implementierungsdetail.

**In Produktion:** nginx bildet `https://example.org/oai` auf `/v1/oai` ab (`location = /oai`). Harvester sollten die kurze URL ohne `/v1` verwenden.

**Migration:** Wenn der OAI-Endpoint ohne `/v1` direkt am FastAPI-App eingehängt werden soll:
```python
# main.py: statt prefix="/v1"
app.include_router(oai.router, prefix="")
```
Das ist ein Breaking Change, sobald Harvester die `/v1/oai`-URL gespeichert haben.
