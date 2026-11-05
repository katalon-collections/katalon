---
type: Decision
title: Cantaloupe-Derivat-Cache auf Platte, Vorschaubilder vorab berechnet
status: accepted
date: 2026-10-14
---

# Kontext

Cantaloupe rendert ein Vorschaubild beim ersten Abruf aus dem Pyramid-TIFF; der Cache lag in
tmpfs und war nach jedem Neustart leer. Der erste Portalbesuch zahlte die Renderzeit.

# Entscheidung

Der Derivat-Cache liegt auf Platte (`CANTALOUPE_CACHE_DIR`, Init-Service `cantaloupe-cache-init`
setzt Eigentümer), tmpfs nur noch per `CANTALOUPE_FILESYSTEMCACHE_PATHNAME=/tmpfs/cache`.
`workers/thumbnail_tasks.py` fordert jede Vorschaugröße nach der Medienverarbeitung einmal an
(`katalon.media.warm_thumbnails`, auch per `katalon media warm-thumbnails`). Das Portal lädt
Vorschaubilder direkt per IIIF-URL über eine cachebare Umleitung, mit `srcset` 2x. Cantaloupe
ist gepinnt (`7.0.22`), Heap 256 MB–1 GB.

# Begründung

Ein persistenter Cache vermeidet erneutes Rendern nach einem Neustart. Vorab
berechnete Vorschaubilder reduzieren die Arbeit beim ersten Abruf; die Ladezeit
hängt weiterhin von Cachezustand, Speicher und Netzverbindung ab.

# Citations

- `backend/src/katalon/workers/thumbnail_tasks.py`
- `docker-compose.yml` (`cantaloupe`, `cantaloupe-cache-init`)
- [Media-Visibility und Cantaloupe-Gate](media-visibility-und-cantaloupe-gate.md), [IIIF-Pyramid-TIFF](iiif-pyramid-tiff.md)
