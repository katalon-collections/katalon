# Plan: XML-Importer mit GUI

**Ziel:** Den bestehenden CSV/Excel-Importer um einen vollständigen XML-Import mit GUI erweitern (XPath-basiertes Mapping, lxml-Parsing, baumförmige Selector-Ansicht im Wizard).

**Stand bei Planerstellung:** 2026-05-22
**Letzte Aktualisierung:** 2026-05-25  
**Entscheidungen (2026-05-22):** Generisches XML (kein Format-Lock), Record-Granularität per User-Klick wählbar (neuer Wizard-Schritt), Upload-Limit massiv hochsetzen.

---

## Übersicht der Issues und ihr aktueller Zustand

| Issue | Bezeichnung | Status | Commit |
|-------|-------------|--------|--------|
| #192 (B1) | Multi-Format-Architektur | ✅ **GESCHLOSSEN** | war bereits in f647e7f |
| #207 (D1) | XMLFormat implementieren | ✅ **GESCHLOSSEN** | dbddb65 |
| #193 (B2) | Mapping-Modell: csv_column → selector | ✅ **GESCHLOSSEN** | ae39aef |
| #206 (D3) | apply_mapping: XPath-Selectors | ✅ **GESCHLOSSEN** | obsolet — XPath-Resolution in parse_flat() |
| #197 (C1) | ScreenImporter.tsx aufteilen | ✅ **GESCHLOSSEN** | a9b410a |
| #205 (D2) | Frontend XML Mapping-UI | ✅ **GESCHLOSSEN** | ed4f181 |
| #194 (B3) | system_fields statt `__idno__` | offen | Phase 4 |
| #198 (C2) | localStorage nur Mapping+Options | offen | Phase 5 |
| #199 (C3.1) | Auto-Mapping-Heuristik | offen | Phase 5 |
| #200 (C3.2) | Live-Preview im TransformModal | offen | Phase 5 |
| #201 (C3.3) | Test mit 10 Zeilen (Rollback) | offen | Phase 5 |
| #202 (C3.4) | Diff-Preview bei Upsert | offen | Phase 5 |
| #203 (C3.5) | Fortschrittsanzeige mit ETA | offen | Phase 5 |
| #204 (C4) | Streaming-Upload >10 MB | offen | Phase 5 |

---

## Phase 0: Aufräumen (< 30 min)

**Aktion:** Issue #192 schließen — die Plugin-Architektur ist bereits vollständig implementiert:
- `backend/src/katalon/services/importer/formats/base.py` — `SourceFormat` ABC, `Selector`, `SourceRecord`
- `formats/csv_format.py`, `formats/excel_format.py` — vollständig
- `formats/registry.py` — vollständig
- `formats/xml_format.py` — **Stub** (raises NotImplementedError) — wird in Phase 1 befüllt

```bash
gh issue close 192 --repo karkraeg/Katalon \
  --comment "Plugin-Architektur ist in f647e7f bereits implementiert. XML-Stub existiert in formats/xml_format.py."
```

---

## Phase 1: XML Backend (Issue #207 — D1) + Upload-Limit

**Ziel:** `xml_format.py` voll implementieren (generisch, namespace-robust), Upload-Limit massiv erhöhen, Tests schreiben.

### Aufgaben

**1.1 Dependency hinzufügen**
```bash
uv add lxml
```

**1.2 Upload-Limit erhöhen**

Datei: `backend/src/katalon/api/v1/importer.py`
- `MAX_SIZE` von 10 MB auf **500 MB** setzen (Wert konfigurierbar via Settings)
- nginx-Proxy: `client_max_body_size` in `docker/nginx.conf` auf **500m** setzen
- FastAPI-Upload-Limit ggf. in `main.py` anpassen wenn nötig

**1.3 `xml_format.py` implementieren**

Datei: `backend/src/katalon/services/importer/formats/xml_format.py`

Namespace-Strategie: **Clark-Notation** intern (`{http://www.loc.gov/mods/v3}title`), aber `label` für die UI als lesbares `ns:local`-Format aus dem Namespace-Präfix-Map ableiten. Wenn kein Präfix vorhanden: Namespace-URL auf letztes Segment kürzen.

```python
from lxml import etree
from typing import Iterator
from .base import Selector, SourceFormat, SourceRecord

def _clark_to_label(tag: str, nsmap: dict) -> str:
    """Convert {ns}local to prefix:local using document's nsmap."""
    if not tag.startswith("{"):
        return tag
    ns, local = tag[1:].split("}", 1)
    # reverse nsmap lookup
    for prefix, uri in nsmap.items():
        if uri == ns:
            return f"{prefix}:{local}" if prefix else local
    # fallback: last segment of namespace URL
    short = ns.rstrip("/").rsplit("/", 1)[-1].rsplit(":", 1)[-1]
    return f"{short}:{local}"

def _rel_xpath(child: etree._Element, elem: etree._Element) -> str:
    """XPath of elem relative to child, using Clark-notation tags."""
    child_path = child.getroottree().getpath(child)
    elem_path = child.getroottree().getpath(elem)
    return elem_path[len(child_path):].lstrip("/")

class XmlFormat(SourceFormat):
    def sniff(self, content: bytes, filename: str) -> bool:
        if filename.lower().endswith(".xml"):
            return True
        stripped = content.lstrip()
        return stripped.startswith(b"<?xml") or stripped.startswith(b"<")

    def list_element_levels(self, content: bytes) -> list[dict]:
        """Return distinct element tag names at each depth level (depth 0 = root).
        Used by frontend to let user choose which element forms a record."""
        root = etree.fromstring(content)
        nsmap = root.nsmap
        levels: dict[int, set[str]] = {}
        for elem in root.iter():
            depth = sum(1 for _ in elem.iterancestors())
            tag = _clark_to_label(elem.tag, nsmap)
            levels.setdefault(depth, set()).add(tag)
        return [{"depth": d, "tags": sorted(tags)} for d, tags in sorted(levels.items())]

    def parse(self, content: bytes, record_xpath: str = "*") -> Iterator[SourceRecord]:
        """Parse XML. record_xpath selects which elements form records (relative to root).
        Default '*' = direct children of root."""
        root = etree.fromstring(content)
        nsmap = {k or "ns": v for k, v in root.nsmap.items()}
        for child in root.xpath(record_xpath, namespaces=nsmap):
            record: SourceRecord = {"__tree__": child}
            for elem in child.iter():
                if elem.text and elem.text.strip():
                    rel = _rel_xpath(child, elem)
                    record[rel] = elem.text.strip()
            yield record

    def list_selectors(self, content: bytes, record_xpath: str = "*",
                       sample_size: int = 50) -> list[Selector]:
        """List XPath selectors relative to record elements, with sample values."""
        root = etree.fromstring(content)
        nsmap = {k or "ns": v for k, v in root.nsmap.items()}
        path_samples: dict[str, list[str]] = {}
        path_labels: dict[str, str] = {}
        for child in list(root.xpath(record_xpath, namespaces=nsmap))[:sample_size]:
            for elem in child.iter():
                if elem.text and elem.text.strip():
                    rel = _rel_xpath(child, elem)
                    label = "/".join(_clark_to_label(p, root.nsmap)
                                     for p in rel.split("/") if p)
                    path_labels[rel] = label
                    path_samples.setdefault(rel, [])
                    if len(path_samples[rel]) < 3:
                        path_samples[rel].append(elem.text.strip())
        return [
            Selector(
                path=p,
                label=path_labels.get(p, p),
                sample=", ".join(samples),
                kind="scalar"
            )
            for p, samples in sorted(path_samples.items())
        ]
```

**1.4 Backend-Endpoint anpassen**

Datei: `backend/src/katalon/api/v1/importer.py`

- Neuer Endpoint `POST /importer/xml-levels` (oder als Teil von `/upload`-Response):  
  Gibt `element_levels` zurück — die Ebenen-Übersicht aus `list_element_levels()`.  
  Frontend nutzt das für die Record-Auswahl.
- Bestehender `/upload`-Endpoint: bei XML gibt `source_type: "xml"` zurück, aber **noch keine** `headers`/`preview` — stattdessen `element_levels` und Hinweis „Bitte Record-Element wählen".
- Neuer Endpoint `POST /importer/xml-selectors`: nimmt `{content_ref, record_xpath}`, gibt `selectors`-Liste zurück. Wird aufgerufen nachdem User das Record-Element gewählt hat.

**1.5 Tests** in `backend/tests/test_xml_format.py`

- `test_sniff_xml_filename()` — `.xml`-Extension erkannt
- `test_sniff_xml_magic()` — `<?xml`-Header ohne Extension erkannt
- `test_list_element_levels()` — Tiefenebenen werden korrekt extrahiert
- `test_parse_generic_xml()` — beliebiges XML, Records mit `__tree__` und rel. XPath-Keys
- `test_parse_with_namespaces()` — MODS-Snippet mit Namespace, Clark-Notation intern, Labels lesbar
- `test_parse_custom_record_xpath()` — `record_xpath="./item"` wählt nicht-direkte Children
- `test_list_selectors_with_samples()` — Selector-Liste enthält Samples und lesbare Labels

**1.6 DoD**
- `uv run pytest backend/tests` — alle Tests grün
- Upload einer `.xml`-Datei gibt `source_type: "xml"` + `element_levels` zurück
- Upload einer 50-MB-Datei wird nicht mit 413 abgelehnt

---

## Phase 2: Mapping-Modell erweitern (Issues #193 + #206 — B2 + D3)

**Reihenfolge:** 193 vor 206 (B2 liefert das Selector-Konzept, D3 nutzt es)

### 2a — Issue #193: csv_column → selector (B2)

Datei: `backend/src/katalon/services/importer_service.py`

- In `MappingRequest`/`MappingEntry`-Pydantic-Schema: Feld `selector: str` hinzufügen
- `csv_column` als optionalen Alias behalten:  
  ```python
  selector: str = Field(alias_priority=...)
  csv_column: str | None = None  # deprecated
  ```
- In `apply_mapping()`: `record.get(entry.selector)` statt direkter Spaltenzugriff
- Für CSV/Excel ändert sich das Verhalten **nicht** (flache Keys)
- Deprecation-Warning loggen wenn `csv_column` benutzt wird
- Tests: bestehende Tests laufen weiterhin durch

### 2b — Issue #206: XPath-Resolution in apply_mapping (D3)

Datei: `backend/src/katalon/services/importer_service.py`

- In `apply_mapping()`: Wenn `SourceRecord` einen `__tree__`-Key hat (lxml-Element):
  ```python
  if "__tree__" in record:
      tree = record["__tree__"]
      result = tree.xpath(selector)
      value = result[0].text if result else None
  else:
      value = record.get(selector)
  ```
- Fallback auf direkten Key-Zugriff wenn kein `__tree__` → CSV/Excel unverändert
- Tests mit XML-Records und XPath-Selectors

**DoD Phase 2:**
- Tests grün
- Bestehende CSV/Excel-Imports weiterhin funktional (manuell verifizieren)
- `csv_column` im JSON-Body wird mit Warning akzeptiert

---

## Phase 3: Frontend (Issues #197 + #205 — C1 + D2)

**Reihenfolge:** C1 (Split) **vor** D2 (XML UI) — die 1021-Zeilen-Datei macht XML-spezifische UI-Erweiterungen schwer wartbar.

### 3a — Issue #197: ScreenImporter aufteilen (C1)

Datei: `frontend/admin/src/components/screens/ScreenImporter.tsx` (aktuell 1021 Zeilen)

Neue Struktur:
```
frontend/admin/src/components/screens/
├── ScreenImporter.tsx          ← nur Wizard-Shell + useReducer
└── importer/
    ├── useImporterState.ts     ← useReducer mit Actions
    ├── StepUpload.tsx
    ├── StepMapping.tsx
    ├── StepDryRun.tsx
    ├── StepExecute.tsx
    └── StepResult.tsx
```

`useImporterState.ts` definiert Actions:
```typescript
type ImporterAction =
  | { type: 'UPLOADED'; payload: UploadResult }
  | { type: 'MAPPING_CHANGED'; payload: MappingEntry[] }
  | { type: 'DRY_RUN_OK'; payload: DryRunResult }
  | { type: 'IMPORT_STARTED' }
  | { type: 'IMPORT_DONE'; payload: TaskStatus }
  | { type: 'RESET' }
```

**DoD:** Verhalten identisch wie vorher, TypeScript kompiliert, manueller Wizard-Durchlauf erfolgreich.

### 3b — Issue #205: XML Mapping-UI (D2)

Neuer Wizard-Schritt **StepXmlRecordSelector.tsx** (zwischen Upload und Mapping, nur bei XML):

**Neuer Schritt: StepXmlRecordSelector.tsx**
- Zeigt die `element_levels` aus der Upload-Response als klickbare Liste
- Jede Tiefenebene wird als Gruppe angezeigt: `Tiefe 1: mods:mods, dc:record, …`
- User klickt auf ein Tag → das wird als `record_xpath` gespeichert
- „Weiter"-Button aktiv sobald ein Element gewählt wurde
- On click: ruft `POST /importer/xml-selectors` mit gewähltem `record_xpath` → lädt Selector-Liste

**Geänderter Schritt: StepMapping.tsx**
- Bei `source_type === "xml"`: linke Spalte zeigt Baum-Ansicht der XPath-Selectors
  - Baumstruktur aus `/`-geteilten Label-Segmenten aufbauen (`mods:titleInfo/mods:title` → Baum)
  - Blattknoten sind anklickbar → werden als Selector ins Mapping übernommen
  - Sample-Wert unter dem Label anzeigen (grau, klein)
- Bei CSV/Excel: unveränderte Spaltenansicht

**Wizard-Schritte neu (bei XML):**
```
Upload → XmlRecordSelector → Mapping → DryRun → Execute → Result
```
**Wizard-Schritte (CSV/Excel):** unverändert
```
Upload → Mapping → DryRun → Execute → Result
```

`useImporterState.ts` erhält neue Action:
```typescript
| { type: 'XML_RECORD_XPATH_SET'; payload: { xpath: string; selectors: Selector[] } }
```

**DoD:**
- XML-Datei hochladen → Record-Auswahl erscheint
- Nach Element-Klick: Baumförmige Selector-Liste im Mapping-Schritt
- Mapping auf Katalon-Felder möglich
- Dry-Run und Import funktionieren mit XML-Daten und XPath-Selectors

---

## Phase 4: system_fields / idno-Cleanup (Issue #194 — B3)

**Zeitpunkt:** Nach Phase 3, kein Blocker für XML-Import

Datei: `backend/src/katalon/services/importer_service.py` + Frontend

- `MappingRequest` erhält optionales `system_fields: dict[str, str]`, z.B. `{"idno": "//*:identifier"}`
- `__idno__`-Pseudofeld noch eine Release-Runde akzeptieren (Deprecation-Warning)
- Frontend: `system_fields.idno` statt `__idno__` in neuem Mapping-Code
- Tests anpassen

---

## Phase 5: UX-Verbesserungen (Issues #198–204 — C2–C4)

Diese Phasen blockieren den XML-Import nicht und können unabhängig oder als eigene Sessions bearbeitet werden.

| Issue | Aufwand | Abhängigkeit |
|-------|---------|--------------|
| #198 (C2) | klein | nach C1 |
| #199 (C3.1) | mittel | nach C1 |
| #200 (C3.2) | mittel | nach C1 |
| #201 (C3.3) | groß | nach Phase 2 (Backend) |
| #202 (C3.4) | groß | nach Phase 2 (Backend) |
| #203 (C3.5) | klein | unabhängig |
| #204 (C4) | groß | unabhängig |

---

## Gesamtreihenfolge (Kritischer Pfad)

```
Phase 0 ✅  →  Phase 1 ✅ (D1)  →  Phase 2 ✅ (B2+D3)
                                          ↓
Phase 3a ✅ (C1)  →  Phase 3b ✅ (D2)  →  XML-Import FERTIG ✅

Phase 4 (B3)  →  nächste Session
Phase 5 (C-Issues)  →  unabhängig, nachrangig
```

**XML-Import-Kernfunktionalität: vollständig implementiert** (Branch: feature/xml-importer)

### Was noch offen ist

- **Phase 4 (#194):** `system_fields`-Dict statt `__idno__`-Pseudo-Feld — sauberere API
- **Phase 5 (#198–204):** UX-Verbesserungen — unabhängig voneinander umsetzbar

---

## Entscheidungen (2026-05-22)

1. **XML-Dialekte:** Generisch — kein Format-Lock. Namespace-Behandlung: Clark-Notation intern, lesbares `prefix:local` für die UI.
2. **Record-Granularität:** User wählt per Klick im neuen `StepXmlRecordSelector`-Schritt. Backend liefert `element_levels` nach Upload.
3. **Upload-Limit:** Auf **500 MB** hochsetzen (Backend + nginx). Issue #204 (Streaming) kommt später für sehr große Dateien.
