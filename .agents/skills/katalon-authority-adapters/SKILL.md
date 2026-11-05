---
name: katalon-authority-adapters
description: >
  Development, testing, deployment, and troubleshooting of custom authority adapters
  (Normdaten-Adapter) for Katalon Collections (the GLAM metadata management system,
  github.com/katalon-collections/katalon — unrelated to katalon.com). Covers the
  AuthoritySource contract (search, fetch, AuthorityHit), deployment options (drop-in
  mount via compose.override.yaml vs. downstream Dockerfile), runtime bootstrap via
  sitecustomize.py, database registration in authority_sources, rate-limiting &
  backoff patterns, and end-to-end integration with Admin UI and Schema Editor. Use
  when asked to create, configure, test, or debug custom normdaten adapters in Katalon
  (e.g., MusicBrainz, Discogs, DNB, local institutional authority files, custom SPARQL endpoints).
license: AGPL-3.0-or-later
---

# Katalon Authority Adapters (Normdaten-Adapter)

Katalon Collections integrates external authority data (GND, GeoNames, VIAF, Wikidata, Getty TGN/AAT, Iconclass) through a modular adapter architecture. Custom and institutional authority sources can be added without modifying the core application image.

```
                         ┌──────────────────────────────────────────────┐
                         │              External System API             │
                         │    (MusicBrainz, Discogs, Custom SPARQL)     │
                         └──────────────────────▲───────────────────────┘
                                                │ HTTPS (search / fetch)
                         ┌──────────────────────┴───────────────────────┐
                         │   Custom AuthoritySource Adapter (Python)    │
                         │    search(query, limit) -> list[AuthorityHit]│
                         │    fetch(external_id)   -> AuthorityHit?     │
                         └──────────────────────▲───────────────────────┘
                                                │
                 ┌──────────────────────────────┴──────────────────────────────┐
                 │                                                             │
┌────────────────┴─────────────────────────────┐             ┌─────────────────┴────────────────────────────┐
│   Option A: Drop-In Development Mount        │             │   Option B: Downstream Docker Image          │
│   compose.override.yaml (volume + PYTHONPATH)│             │   Dockerfile (uv pip install / package)      │
│   sitecustomize.py bootstrap hook            │             │   Self-contained deployment           │
└────────────────┬─────────────────────────────┘             └─────────────────┬────────────────────────────┘
                 │                                                             │
                 └──────────────────────────────┬──────────────────────────────┘
                                                │
                                                ▼
                         ┌──────────────────────────────────────────────┐
                         │     Katalon API Runtime (authority_service)  │
                         │   _BUILTIN + authority_sources (DB Table)   │
                         └───────┬──────────────────────────────┬───────┘
                                 │                              │
         GET /v1/authorities/    ▼                              ▼   GET /v1/authorities/search|fetch
         ┌──────────────────────────────┐             ┌──────────────────────────────┐
         │ Admin: Einstellungen         │             │ Record & Vocab Formulare     │
         │ - Normdatenquellen Übersicht │             │ - Autocomplete Lookup        │
         │ - Verbindung testen          │             │ - Übernahme in Metadaten     │
         │ Schema-Editor: Quellenauswahl│             │ - Persistente MBID/PID & URI │
         └──────────────────────────────┘             └──────────────────────────────┘
```

---

## 1. Der Adapter-Vertrag (`AuthoritySource`)

Jeder Adapter muss die abstrakte Basisklasse `AuthoritySource` aus `katalon.integrations.authority` implementieren:

```python
from __future__ import annotations
from typing import Any
import httpx
from katalon.integrations.authority import AuthorityHit, AuthoritySource

class MeinAdapter(AuthoritySource):
    source_id: str = "mein-system"

    def __init__(self, source_id: str = "mein-system", **kwargs: Any) -> None:
        self.source_id = source_id

    async def search(self, query: str, limit: int = 10) -> list[AuthorityHit]:
        """Sucht in der externen Quelle und liefert normierte Treffer zurück."""
        ...

    async def fetch(self, external_id: str) -> AuthorityHit | None:
        """Holt einen Einzelsatz per persistenter ID. Liefert None bei 404."""
        ...
```

### Die `AuthorityHit`-Datenstruktur

| Feld | Typ | Beschreibung | Beispiel |
|---|---|---|---|
| `source` | `str` | Eindeutige ID der Quelle | `"musicbrainz"` |
| `external_id` | `str` | Persistente ID / UUID / Notation | `"24f1766e-9635-4d58-a4d4-9413f9f98a4c"` |
| `label` | `str` | Angezeigter Hauptname / Werktitel | `"Johann Sebastian Bach"` |
| `description` | `str` | Erläuterung (Disambiguation, Typ, Lebensdaten) | `"Komponist (1685–1750)"` |
| `extra` | `dict` | Beliebige Zusatzdaten (`uri`, `coordinates`, etc.) | `{"uri": "https://...", "coordinates": {"lat": ..., "lng": ...}}` |

---

## 2. Bereitstellungswege

### Weg A: Drop-In via `compose.override.yaml` (Entwicklung & Lokaler Test)

Ermöglicht sofortiges Entwickeln und Testen ohne Container-Rebuild.

1. **Adapter-Ordner anlegen**: `adapters/<name>/`
2. **`compose.override.yaml` anpassen**:
   ```yaml
   services:
     api:
       volumes:
         - ./themes:/var/lib/katalon/themes:ro
         - ./adapters/<name>:/app/adapters/<name>:ro
       environment:
         PYTHONPATH: /app/adapters/<name>
   ```
3. **`sitecustomize.py` im Adapter-Ordner platzieren**:
   Wird beim Start von Python im Container automatisch ausgeführt und registriert die Quelle in Katalons Runtime:
   ```python
   from katalon.services import authority_service
   from mein_paket.adapter import MeinAdapter

   authority_service._BUILTIN["mein-system"] = MeinAdapter()
   authority_service._LABELS["mein-system"] = "Mein System"
   authority_service.invalidate_cache()
   ```
4. **Container neu starten**:
   ```bash
   docker compose up -d api
   ```

### Weg B: Downstream-Image (Produktion & CI/CD)

Ein Downstream-Dockerfile basierend auf dem offiziellen Katalon-API-Image:

```dockerfile
ARG KATALON_API_IMAGE=ghcr.io/katalon-collections/katalon-api:1.19.2
FROM ${KATALON_API_IMAGE}

USER root
COPY . /tmp/mein_adapter
RUN uv pip install --system /tmp/mein_adapter && rm -rf /tmp/mein_adapter
RUN cp -f /tmp/mein_adapter/sitecustomize.py "$(python3 -c 'import site; print(site.getsitepackages()[0])')/sitecustomize.py" 2>/dev/null || true
USER app
```

---

## 3. Registrierung in der Datenbank (`authority_sources`)

In der PostgreSQL-Tabelle `authority_sources` werden die Quellen für den Admin-Bereich und den Schema-Editor persistent verwaltet:

```sql
INSERT INTO authority_sources (id, label, adapter_class, config, is_enabled)
VALUES (
    'mein-system',
    'Mein System',
    'mein_paket.adapter.MeinAdapter',
    '{"custom_option": "wert"}',
    true
)
ON CONFLICT (id) DO UPDATE SET
    label = EXCLUDED.label,
    adapter_class = EXCLUDED.adapter_class,
    config = EXCLUDED.config,
    is_enabled = EXCLUDED.is_enabled;
```

Der JSONB-Inhalt von `config` wird bei der dynamischen Instanziierung als `**kwargs` an den Konstruktor des Adapters übergeben.

---

## 4. Wichtige Best Practices für GLAM-Adapter

1. **Aussagekräftiger `User-Agent`**:
   Viele APIs (MusicBrainz, Wikidata, Wikimedia) verlangen zwingend einen Identifikationsheader im Format `AppName/Version (URL; ContactEmail)`. Generiere diesen dynamisch aus `settings.katalon_base_url` und `settings.default_admin_email`.
2. **Rate-Limiting & Backoff**:
   Öffentliche APIs (z. B. MusicBrainz mit 1 Request/Sekunde) antworten bei zu schnellen Abfragen mit HTTP 503 (`Service Unavailable`). Fange 503 mit einem kurzen `asyncio.sleep(1.1)` und 1 Retry ab.
3. **Fehlerbehandlung**:
   Belasse es bei echten Netzwerk-/Serverfehlern bei `r.raise_for_status()`. Die Katalon-API fängt `httpx.HTTPError` ab und wandelt ihn in ein sauberes deutsches `502 Bad Gateway` für das Frontend um.
4. **Geo-Koordinaten bei Orten**:
   Werden Koordinaten als `extra["coordinates"] = {"lat": float, "lng": float}` bereitgestellt, können Formulare (wie bei GeoNames) eine klickbare Vorschaukarte rendern.
5. **Persistente URIs**:
   Lege immer die vollständige Web-URI im `extra["uri"]`-Feld ab, damit Datensätze direkt auf das Quellsystem verlinken können.

---

## 5. Fehlerdiagnose (Troubleshooting)

- **Adapter erscheint nicht im Admin-Dropdown (*Einstellungen → Normdatenquellen*) oder `PATCH /v1/authorities/{id}` liefert 404 für die eigene Quelle**:
  - **Behoben in Katalon Core > 1.35.0** (siehe `CHANGELOG.md`, Abschnitt `[Unreleased]`): `GET /v1/authorities/` und `PATCH /v1/authorities/{id}` berücksichtigen jetzt auch Quellen, die ausschließlich als `authority_sources`-Zeile mit eigenem `adapter_class` existieren (Weg aus Abschnitt 3), ohne Eintrag in `_BUILTIN`. Reines DB-`INSERT` reicht dann aus — kein `sitecustomize.py`-Workaround nötig, sobald diese Core-Version läuft.
  - **Auf älteren Core-Versionen (≤ 1.35.0)**: `GET /v1/authorities/` iterierte nur über `authority_service.list_sources()` (hartkodierte `_BUILTIN`-Liste) und `PATCH` lehnte reine DB-Quellen mit 404 ab. Workaround: `sitecustomize.py` (Weg A, Abschnitt 2) trägt die Quelle zusätzlich in `authority_service._BUILTIN` ein, damit beide Endpunkte sie erkennen. Nach einem Core-Update auf > 1.35.0 kann dieser Workaround entfernt werden — reine DB-Registrierung (Abschnitt 3) genügt dann.
- **Admin-Button *Verbindung testen* schlägt fehl**:
  - Prüfe, ob die Test-URL oder der Suchbegriff für die Quelle funktioniert. Katalon sendet standardmäßig die Query `"test"`, wenn keine spezifische Test-Query in `ScreenSettings.tsx` hinterlegt ist.
- **`ModuleNotFoundError` beim Starten des Containers**:
  - Prüfe `PYTHONPATH` in `compose.override.yaml` und die Berechtigungen (Dateien müssen für User `app` / UID 1000 lesbar sein).
- **Änderungen in der DB greifen nicht sofort**:
  - `authority_service.invalidate_cache()` aufrufen oder API-Container neu starten.
