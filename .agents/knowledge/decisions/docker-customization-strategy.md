---
type: Decision
title: Docker-first Customization — Volume Mounts statt Image-Rebuilds
description: Branding und Authority-Adapter werden über docker-compose.override.yml und Volume Mounts angepasst, damit docker compose pull ohne Rebuild funktioniert.
tags: [deployment, docker, customization]
timestamp: 2026-05-08T17:50:29Z
---

# Kontext

CollectiveAccess löst Instanz-Anpassung über PHP-Theme-Overlays,
InvenioRDM über Python-Entry-Points. Katalons Docker-first
Deployment-Modell (siehe [Tech-Stack](tech-stack.md)) braucht dafür
einen eigenen Mechanismus, weil Docker-Updates atomar sind — eigene
Anpassungen müssen ein Image-Update überleben können, ohne dass Nutzer
ihr eigenes Image bauen müssen (Issue #105).

# Entscheidung

- **MVP-Scope**: Branding (Logo, Farben, Favicon) + Authority-Adapter.
  Templates und eigene Feldtypen sind Post-MVP.
- **Konfiguration**: `docker-compose.override.yml`-Pattern, damit die
  Haupt-`docker-compose.yml` sauber und update-fähig bleibt.
- **Statische Assets**: `custom/`-Verzeichnis mit `static/` und
  `templates/`-Unterordnern, als Volume gemountet; eigene Assets haben
  Priorität vor eingebauten, überleben `docker compose pull` ohne
  Rebuild.
- **Plugins (MVP)**: Volume-gemountetes Plugin-Verzeichnis + PYTHONPATH-
  Eintrag, kein Rebuild nötig.
- **Plugins (Produktion)**: Downstream-Docker-Image (`FROM katalon-api`)
  mit `pip install` — sauberer, aber Rebuild bei jedem Update.
- **Update-Flow**: `docker compose pull` → `docker compose up -d` →
  `alembic upgrade head`. Breaking Changes werden versioniert in
  `UPGRADING.md` dokumentiert (Rails-/Nextcloud-Stil).
- Manuelles Mergen von `.env`- und `docker-compose.yml`-Änderungen bei
  Updates bleibt Nutzerverantwortung.

# Begründung

Volume Mounts + Override-Datei lösen den Zielkonflikt zwischen
"einfach für MVP" und "sauber für Produktion", indem beide Wege parallel
angeboten werden: schnell und ohne Rebuild für die meisten Fälle,
Downstream-Image für Institutionen mit eigener Build-Pipeline.

# Citations

[1] GitHub Issue #105
[2] Session-Entscheidung 2026-05-08: "Docker-first customization strategy: Volume mounts, override files, and plugin architecture"
