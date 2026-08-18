# API-Dokumentation

Katalon bietet eine automatisch generierte OpenAPI-basierte API-Dokumentation.

## Interaktive Docs (laufende Instanz)

Sobald der API-Service läuft, sind die interaktiven Docs erreichbar unter:

- Swagger UI: `/api/docs`
- ReDoc: `/api/redoc`
- OpenAPI-Schema: `/api/openapi.json`

Beispiel für einen lokalen Dev-Stack:

```text
http://localhost:8000/api/docs
http://localhost:8000/api/redoc
http://localhost:8000/api/openapi.json
```

Über den Produktions-nginx sind die URLs:

```text
https://deine-domain.de/api/docs
https://deine-domain.de/api/redoc
https://deine-domain.de/api/openapi.json
```

## Statisches OpenAPI-Schema

Das Repository enthält eine eingecheckte, versionierte Kopie des Schemas:

- [`openapi.json`](../../openapi.json) (im Repository-Root)

## Schema neu generieren

Nach Änderungen an Endpoints, Pydantic-Schemas oder Tags das Schema aktualisieren:

```bash
uv run python scripts/gen_openapi.py
```

Ein alternativer Ausgabepfad lässt sich als Argument übergeben:

```bash
uv run python scripts/gen_openapi.py /tmp/openapi.json
```

Das Skript setzt intern Dummy-Werte für Secrets/URLs, damit die App importiert
werden kann, ohne dass eine Datenbank oder Elasticsearch erreichbar sein muss.
