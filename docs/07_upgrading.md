# Katalon – Updates und Datenpflege

Dieses Dokument erklärt, wie Katalon aktualisiert wird, was dabei mit deinen Daten und Anpassungen passiert, und worauf du bei bestimmten Versionssprüngen achten musst.

## Das Grundprinzip: Docker-first

Katalon läuft vollständig in Docker-Containern. Was das für Updates bedeutet, lässt sich am einfachsten so erklären:

**Code und Daten sind getrennt.**

- Der **Code** (Backend, Frontend, nginx) steckt in Docker-Images. Diese Images werden von Katalon veröffentlicht und können mit einem einzigen Befehl aktualisiert werden.
- Die **Daten** (Datensätze, Schemata, Mediendateien, Konfiguration) liegen in Docker Volumes und in deiner `.env`-Datei — komplett außerhalb der Images. Ein Image-Update berührt sie nicht.

Das bedeutet: Ein Katalon-Update überschreibt keine deiner Daten und keine deiner Konfigurationen. Was du in der Admin-Oberfläche eingestellt hast — Felder, Vokabulare, Datensätze — bleibt erhalten.

Was du manuell verwalten musst: deine `.env`-Datei und eventuelle Anpassungen an `docker-compose.yml`. Dazu weiter unten mehr.

## Standard-Update (keine Breaking Changes)

Das ist der Normalfall für Bugfix- und Minor-Releases (z.B. 1.0.1 → 1.0.2, 1.1.0 → 1.2.0).

```bash
# Neueste Images herunterladen
docker compose pull

# Container mit neuen Images neu starten
docker compose up -d

# Datenbankmigrationen anwenden (falls vorhanden)
docker compose exec api alembic upgrade head
```

Fertig. Deine Daten sind unberührt. Die Migrationen (`alembic upgrade head`) sind immer sicher anzuwenden — sie fügen höchstens neue Spalten oder Tabellen hinzu, löschen nie Daten.

**Wann ist `alembic upgrade head` nötig?** Immer, wenn du weißt, dass ein Release neue Datenbankfelder einführt. Im Zweifel: einfach ausführen, es passiert nichts Schlimmes wenn keine Migration offen ist.

## Breaking Changes

Manche Updates erfordern einen manuellen Schritt, weil sich `.env`-Variablen oder die Struktur von `docker-compose.yml` geändert haben. Das passiert bei Major-Releases (z.B. 1.x → 2.0).

Solche Änderungen werden in `UPGRADING.md` (im Repository-Root) dokumentiert — mit versionierten Abschnitten, die genau beschreiben, was zu tun ist. **Vor jedem Major-Update: `UPGRADING.md` lesen.**

### Neue `.env`-Variable hinzugekommen

Beispiel: Eine neue Version führt die Variable `MAIL_FROM` ein.

1. Schau in `.env.example`, welche neuen Variablen es gibt.
2. Füge sie in deine `.env` ein.
3. Dann erst: `docker compose pull && docker compose up -d`.

Tipp: Ein diff zwischen deiner `.env` und der aktuellen `.env.example` zeigt sofort, was fehlt:
```bash
diff .env .env.example
```

### `docker-compose.yml` hat sich geändert

Wenn du `docker-compose.yml` nicht angepasst hast, kannst du sie einfach übernehmen (`git pull`).

Wenn du eigene Änderungen gemacht hast (z.B. Ports, Volume-Pfade), nutze `docker-compose.override.yml` für deine Anpassungen — so bleibt die Haupt-`docker-compose.yml` sauber und kann ohne Konflikte aktualisiert werden:

```yaml
# docker-compose.override.yml — deine Anpassungen, wird von Docker Compose
# automatisch zusammengeführt, nie von Updates überschrieben
services:
  nginx:
    ports:
      - "8443:443"
```

## Was bei einem Update erhalten bleibt

| Was | Warum sicher |
|---|---|
| Alle Datensätze (Objekte, Entitäten, Orte, Ereignisse) | PostgreSQL-Volume |
| Schemata und Felddefinitionen | PostgreSQL-Volume |
| Vokabulare | PostgreSQL-Volume |
| Konfigurierte Normdatenquellen | PostgreSQL-Volume |
| Mediendateien | Media-Volume |
| Deine `.env` | Liegt außerhalb der Container |
| `docker-compose.override.yml` | Liegt außerhalb der Container |

## Was du nach einem Update prüfen solltest

- [ ] Admin-Oberfläche öffnen und kurz durch die Hauptbereiche navigieren
- [ ] Einen Datensatz öffnen und speichern (prüft Schreib-Zugriff auf DB)
- [ ] Elasticsearch-Status: `docker compose exec api curl -s localhost:9200/_cluster/health`
- [ ] Logs auf Fehler prüfen: `docker compose logs --tail=50 api`

## Vollständige Neuinstallation (Daten löschen)

Wenn du eine Instanz komplett zurücksetzen willst — zum Beispiel in einer Test-Umgebung — findest du die Anleitung in `dev_reset.md`. Für Produktionsdaten: **niemals** ohne Backup, und lies vorher `dev_reset.md` komplett durch.

## Backup vor einem Update

Vor jedem größeren Update empfiehlt sich ein Datenbank-Dump:

```bash
docker compose exec db pg_dump -U katalon katalon > backup_$(date +%Y%m%d).sql
```

Den Dump außerhalb des Servers aufbewahren. Eine automatisierte Backup-Strategie wird in `04_produktion.md` beschrieben.
