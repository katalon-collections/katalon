# Zu Katalon Collections beitragen

Beiträge zu Code, Tests, Dokumentation und Fehlerberichten sind willkommen.
Katalon Collections ist ein selbst betriebenes Metadatenmanagementsystem für
Museen, Archive, Bibliotheken und Sammlungen. Die Projektpflege und
Release-Entscheidungen liegen derzeit beim Maintainer; diese Anleitung
beschreibt den Einstieg für externe Beiträge.

## Einen Beitrag vorbereiten

Suche zunächst nach einem passenden Issue im
[öffentlichen Repository](https://github.com/katalon-collections/katalon/issues).
Ein Fehlerbericht sollte Version oder Commit, Reproduktionsschritte,
erwartetes und tatsächliches Verhalten sowie relevante, bereinigte Logs
enthalten. Beispieldaten sollten klein sein und keine vertraulichen Inhalte
enthalten. Sicherheitsprobleme werden nach [SECURITY.md](SECURITY.md) privat
gemeldet.

Kleine Korrekturen können direkt als Pull Request vorgeschlagen werden.
Bei neuen Funktionen, Änderungen am Datenmodell, an Berechtigungen oder an
bestehenden Schnittstellen zuerst Problem und Lösungsansatz in einem Issue
abstimmen. Beschreibe dabei den konkreten Anwendungsfall und Auswirkungen auf
vorhandene Daten oder Integrationen.

Bei größeren Architekturänderungen gehört ein Konzeptvorschlag vor den Code:
Problem, Zielgruppe, bestehende Verträge, vorgeschlagener Ansatz, Alternativen,
Nicht-Ziele, Auswirkungen auf Daten und Schnittstellen sowie Abnahmekriterien.
Beschreibe Migration und Wiederherstellung, wenn vorhandene Daten betroffen sind.

Für Änderungen an sichtbaren Abläufen lege Mockups, Wireframes oder einen
begrenzten Prototyp vor. Zeige Hauptablauf, leere und Fehlerzustände,
Tastaturbedienung und schmale Ansichten. Eine rein technische Änderung kann
stattdessen durch ein Komponenten- oder Datenflussdiagramm erläutert werden.
Konzept und Richtung werden vor der größeren Implementierung abgestimmt;
kleine Korrekturen benötigen kein eigenes Konzeptpapier.

Erstelle einen Fork des öffentlichen Repositorys und einen eigenen Branch für
den Beitrag. Halte den Umfang auf eine zusammengehörige Änderung begrenzt.
Maintainer integrieren Beiträge in den Entwicklungs- und Releaseprozess;
Versionssprünge, Release-Tags und die Veröffentlichung sind eigene Schritte.

## Projektkontext lesen

Die [README](README.md) erklärt Funktionsumfang und Installation. Vor Arbeiten
mit einem Coding-Agent gelten die Regeln in `AGENTS.md`, soweit sie im
jeweiligen Checkout enthalten sind. Eine optionale private Maintainer-Ergänzung
wird nur gelesen, wenn sie tatsächlich im Checkout vorhanden ist; externe
Beiträge benötigen weder diese Datei noch Zugriff auf das private Repository.

Der ausführliche Kontext ist im Entwicklungscheckout so aufgeteilt:

| Ablage | Inhalt |
|---|---|
| `.agents/DEV.md` | Lokales Setup, Werkzeuge und Testwege |
| `.agents/rules/` | Backend- und Frontend-Konventionen |
| `.agents/knowledge/decisions/` | Architekturentscheidungen und ihre Begründung |
| `almanac/` | Aktuelle Architektur, Abläufe und Verträge mit Codebelegen |
| `docs/` | Technische Entwickler- und Betriebsanleitungen |

`.agents/`, `almanac/` und die Agent-Regeln sind im öffentlichen Repository
enthalten, `docs/` bisher nicht. Fehlt in deinem Checkout Kontext, beschreibe
im Issue oder PR, welcher Kontext für den Beitrag benötigt wird. Private Issue-Links sind keine
Voraussetzung für einen externen Beitrag. Die
[Anwenderdokumentation](https://katalon-collections.github.io/katalon-docs/)
liegt in einem separaten Repository.

Aktueller Code beschreibt das tatsächliche Verhalten. Wenn er einer gültigen
Entscheidung widerspricht, benenne die Abweichung, bevor du sie als neues
gewünschtes Verhalten übernimmst. Agent-Werkzeuge wie CodeGraph oder CodeAlmanac
können beim Lesen helfen; Änderungen müssen auch anhand der Quelldateien und
Tests nachvollziehbar sein.

## Lokal entwickeln

Der Docker-Dev-Stack benötigt Docker mit Compose v2. Im geklonten Repository:

```bash
cp .env.example .env
```

Konfiguriere die erforderlichen Werte anhand der Kommentare in `.env.example`.
Verwende eigene Entwicklungswerte für Passwörter und Secrets. Für projektlokale
Dateien können `MEDIA_ROOT=./media` und `BACKUP_ROOT=./backups` gesetzt werden.
Starte danach den Stack:

```bash
make dev
```

Backend und Frontends laufen mit Live-Reload. Die Zugänge sind:

- Admin: <http://localhost:4000>
- Portal: <http://localhost:4001>
- API-Dokumentation: <http://localhost:8000/api/docs>

Der API-Entrypoint führt die Alembic-Migrationen aus. Bei Datenbankfehlern zuerst
Logs und Ursache prüfen. Datenbank-Volumes zu löschen ist kein Reparaturweg.

Für Host-Entwicklung werden Python 3.14+, `uv` und für die Frontends Node.js
sowie die in den jeweiligen `package.json`-Dateien genannte pnpm-Version
benötigt. Der Frontend-CI-Stand verwendet Node.js 22. Medienbezogene
Backendtests benötigen zusätzlich eine passende libvips-Installation.

## Änderungen prüfen

Führe die zur Änderung passenden Prüfungen aus und dokumentiere Ergebnis und
Grenzen im PR. Ein kleiner Dokumentationsfix braucht keine vollständige
Anwendungstestsuite. Neue Logik oder ein Bugfix braucht eine gezielte Prüfung,
die das neue Verhalten oder die Regression tatsächlich abdeckt.

### Backend

Abhängigkeiten mit Dev-Extras installieren und aus `backend/` testen:

```bash
cd backend
uv sync --extra dev
KATALON_SECRETS_KEY="test-katalon-secrets-key-32-chars" \
  uv run pytest tests/test_schema_service.py
```

Ersetze das Beispielmodul durch die betroffenen Tests. Der Testschlüssel muss
vor Test-Collection gesetzt sein und mindestens 32 Zeichen haben. Er ist ein
Testwert, kein Secret für eine Installation. Datenbank-Integrationstests
starten einen isolierten PostGIS-Container über Testcontainers und benötigen
einen erreichbaren Docker-Daemon; weitere Anforderungen hängen vom Testmodul ab.

Python-Code wird mit Ruff geprüft. Installierte Dev-Werkzeuge lassen sich
beispielsweise mit `uv run ruff check src tests` aus `backend/` ausführen.
Bei API-Änderungen gehört die aktualisierte `openapi.json` dazu; der Generator
liegt unter `scripts/gen_openapi.py`.

### Frontends

Aus `frontend/admin/` oder `frontend/portal/`:

```bash
pnpm install --frozen-lockfile
pnpm test
pnpm exec tsc --noEmit
pnpm build
```

Für Admin zusätzlich `pnpm lint` ausführen. Portal hat derzeit kein eigenes
`lint`-Skript. Begrenze Tests bei kleinen Änderungen auf die betroffenen
Module; neue sichtbare Admin-Texte brauchen deutsche und englische Einträge.
Für Layout- und Interaktionsänderungen die manuellen Prüfschritte und,
wenn durchgeführt, deren Ergebnis angeben. Automatisierte Tests ersetzen
keine visuelle Abnahme.

## Code und Dokumentation

Nutze vorhandene Services, Schemata und UI-Komponenten. Neue Abstraktionen oder
Abhängigkeiten brauchen einen konkreten Bedarf. Backend-Handler, Services,
Integrationen und Worker behalten ihre bestehenden Zuständigkeiten.

Öffentliche Ausgaben müssen die gemeinsame öffentliche Projektion verwenden.
Sichtbarkeitsregeln, Berechtigungen, Versionsprüfung und der Schutz bestehender
Daten gelten auch für neue Import-, Export- und Hintergrundpfade. Migrationen
müssen Auswirkungen auf vorhandene Daten und Wiederherstellung erklären.

Wenn eine Änderung dokumentiertes Verhalten betrifft, aktualisiere die
betroffenen Verträge und Anleitungen. Eine neue Architekturentscheidung
gehört zuerst in die Entscheidungsakte. Bewahre weiterhin relevante Gründe
und Grenzen; erledigte Aufgabenprotokolle und separate Doku-Pflegelogs sind
nicht nötig. Betrifft die Änderung die Bedienung, benenne auch die erforderliche
Anpassung der externen Anwenderdokumentation.

Alle sichtbaren Texte in Admin und Portal sind übersetzbar und liegen auf Deutsch
und Englisch vor. Wie eine weitere Oberflächensprache ergänzt wird, beschreibt
[docs/11_oberflaechensprachen.md](docs/11_oberflaechensprachen.md).

Neue Python-/TypeScript-Code-Dateien und E2E-Tests verwenden die im Repository
vorgeschriebenen SPDX- und Copyright-Header. Für Beiträge gilt die Projektlizenz
[AGPL-3.0-or-later](LICENSE).

## Einen Pull Request einreichen

Ein PR sollte Problem, resultierendes Verhalten und Prüfung verständlich
beschreiben. Verweise auf das zugehörige öffentliche Issue mit vollständiger
URL, wenn die Zuordnung sonst mehrdeutig ist. Ergänze relevante Auswirkungen
auf Daten, Konfiguration und Integrationen sowie offene Abnahmeschritte.

Übernimm keine fremden oder nicht zur Änderung gehörenden Arbeitsstände.
Vermeide Versions-Bumps und Release-Tags ohne Abstimmung. Bei Verwendung eines
Coding-Agenten prüft die einreichende Person die erzeugten Änderungen und
verantwortet den Beitrag wie jeden anderen PR.
