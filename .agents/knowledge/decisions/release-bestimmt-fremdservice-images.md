---
type: Decision
title: Das Katalon-Release bestimmt die Images der Fremdservices, katalon-cli führt aus
status: accepted
date: 2026-10-24
---

# Kontext

Die Versionen von Postgres, Redis, Elasticsearch, Cantaloupe, nginx und Caddy standen an drei
Stellen: `docker-compose.yml`, `charts/katalon/values.yaml` und fest im Template von katalon-cli.
`requires` in `release-meta.toml` nannte Elasticsearch `>=8.15`, während alle Stacks 8.13.4
liefen; niemand prüfte den Wert. Eine neue ES-Version für ein Katalon-Release hätte eine neue
CLI-Version samt `minimum_installer_version` gebraucht.

# Entscheidung

`[images]` in `release-meta.toml` legt die Images (`repository:tag`) fest, `katalon-release.json`
liefert sie als `images`. katalon-cli (ab 0.4.0) rendert sie in `compose.yaml`, speichert sie je
Version in `installation.json` und prüft vor `update` die wirksamen Images (inkl.
`compose.override.yaml`): Abbruch bei Major-Wechsel von Postgres/Elasticsearch und bei verletztem
`requires`. `requires` beschreibt, womit Katalon technisch läuft, und gilt erst ab Releases mit
`images`. Rollback behält ein neueres Elasticsearch derselben Major-Version.

# Begründung

Katalon weiß, welche Infrastruktur es braucht; die CLI ist nur ausführender Teil. Ein Test in
Katalon hält Compose, Helm und `[images]` synchron und prüft sie gegen `requires`, damit es nur
eine Quelle gibt. Major-Upgrades von Datenservices bleiben bewusst manuell, bis einer ansteht
(YAGNI): Postgres braucht Dump/Restore, ES öffnet fremde Major-Datenverzeichnisse nicht.

# Konsequenzen

- Neue Version eines bestehenden Fremdservice: `[images]`, `docker-compose.yml` und Helm-Values
  ändern, sonst nichts. Kein CLI-Release nötig.
- Neuer Service, Ports oder Volumes: weiterhin CLI-Template ändern, `compose_revision` und
  `minimum_installer_version` hochziehen.
- Die Fallback-Images in `ReleaseImages` (katalon-cli) bleiben eingefroren auf dem Stand bis
  Katalon 1.46.0.

# Citations

- `release-meta.toml` (`[images]`, `[requires]`)
- `scripts/gen_release_metadata.py`
- `backend/tests/test_release_metadata.py`
- katalon-cli: `src/katalon_cli/core/images.py`, `core/release.py`, `templates/compose.yaml.j2`
- `almanac/decisions/operations/katalon-cli-distribution.md`
