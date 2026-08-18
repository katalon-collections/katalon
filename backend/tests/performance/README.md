# Performance-Tests mit Locust

Dieser Ordner enthält [Locust](https://locust.io/)-Lasttests für Katalon.

## Installation

Locust ist als Dev-Dependency in `backend/pyproject.toml` hinterlegt.

```bash
cd backend
uv sync --extra dev
```

## Ausführen

### Gegen den lokalen Dev-Stack (API direkt auf Port 8000)

```bash
cd backend
KATALON_LOCUST_HOST=http://localhost:8000 \
KATALON_LOCUST_EMAIL=admin@example.org \
KATALON_LOCUST_PASSWORD=<passwort> \
    uv run locust -f tests/performance/locustfile.py
```

Öffne danach http://localhost:8089, setze Host und Starte den Schwarm.

### Gegen die Produktions-URL (über nginx)

```bash
cd backend
KATALON_LOCUST_HOST=https://example.org \
KATALON_LOCUST_EMAIL=admin@example.org \
KATALON_LOCUST_PASSWORD=<passwort> \
    uv run locust -f tests/performance/locustfile.py
```

### Nur öffentlichen Portal-Traffic testen

Wenn keine Admin-Zugangsdaten vorhanden sind oder nur die öffentlichen
Endpunkte belastet werden sollen:

```bash
uv run locust -f tests/performance/locustfile.py --user-classes PublicPortalUser
```

## Szenarien

- `PublicPortalUser` (Gewicht 4): Gesundheitscheck, öffentliche Suche,
  Objektlisten, Portal-Konfiguration, Seiten.
- `AdminUser` (Gewicht 1): Login, Schema lesen, Objekte/Entitäten listen,
  Vokabulare, Objekt anlegen + lesen, Admin-Suche.

## Konfiguration per Umgebungsvariable

| Variable | Default | Bedeutung |
|---|---|---|
| `KATALON_LOCUST_HOST` | `http://localhost:8000` | Basis-URL der Katalon-Instanz |
| `KATALON_LOCUST_EMAIL` | `admin@example.org` | Admin-E-Mail für Login |
| `KATALON_LOCUST_PASSWORD` | – | Admin-Passwort |

## Headless / CI

```bash
uv run locust -f tests/performance/locustfile.py \
    --host http://localhost:8000 \
    --headless -u 10 -r 2 -t 60s \
    --html /tmp/locust-report.html
```
