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

## Lastprofile (Smoke / Normal / Load)

Statt Nutzerzahl/Rate/Dauer manuell über `-u`/`-r`/`-t` zu setzen, wählt
`KATALON_LOCUST_PROFILE` eines der in `locustfile.py` definierten Profile:

| Profil | Nutzer | Spawn-Rate | Dauer |
|---|---|---|---|
| `smoke` | 5 | 1/s | 60 s |
| `normal` | 50 | 5/s | 5 min |
| `load` | 100 | 10/s | 10 min |

Heavy-Load-, Stress- und Soak-Profile (~500 Nutzer, Langzeitläufe) sind
bewusst nicht enthalten — siehe Ticket #382 für die Begründung (Infrastruktur-
/Wartungsaufwand steht aktuell in keinem Verhältnis zu einem konkreten Bedarf).

```bash
cd backend
KATALON_LOCUST_HOST=http://localhost:8000 \
KATALON_LOCUST_PROFILE=smoke \
    uv run locust -f tests/performance/locustfile.py --headless
```

## Schwellenwert (CI-Gate)

Am Ende jedes Laufs prüft ein `events.quitting`-Handler die Fehlerrate gegen
`KATALON_LOCUST_MAX_FAIL_RATIO` (Default `0.01` = 1 %) und setzt bei
Überschreitung den Prozess-Exit-Code auf `1` — das lässt den Locust-Lauf in CI
fehlschlagen, ohne ein zweites Tool einzuführen.

## Konfiguration per Umgebungsvariable

| Variable | Default | Bedeutung |
|---|---|---|
| `KATALON_LOCUST_HOST` | `http://localhost:8000` | Basis-URL der Katalon-Instanz |
| `KATALON_LOCUST_EMAIL` | `admin@example.org` | Admin-E-Mail für Login |
| `KATALON_LOCUST_PASSWORD` | – | Admin-Passwort |
| `KATALON_LOCUST_PROFILE` | – | `smoke` \| `normal` \| `load`, siehe oben |
| `KATALON_LOCUST_MAX_FAIL_RATIO` | `0.01` | Fehlerrate, ab der der Lauf als fehlgeschlagen gilt |

## Headless / CI

```bash
uv run locust -f tests/performance/locustfile.py \
    --host http://localhost:8000 \
    --headless -u 10 -r 2 -t 60s \
    --html /tmp/locust-report.html
```

Der geplante `load-smoke`-GitHub-Actions-Workflow (`.github/workflows/load-smoke.yml`)
führt das `smoke`-Profil wöchentlich gegen die Staging-Umgebung aus — nicht bei
jedem Push, siehe Workflow-Kommentar.
