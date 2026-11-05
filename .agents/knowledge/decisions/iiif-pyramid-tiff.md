---
type: Decision
title: Pyramid-TIFF-Ableitung bei Media-Upload — Original bleibt, Pyramide zusätzlich
description: Zusätzliche Pyramid-TIFF-Ableitung via pyvips für Random-Access in Cantaloupe; Original bleibt erhalten. Heute relative storage_key/iiif_storage_key statt der ursprünglichen Pfadspalten.
tags: [media, iiif, cantaloupe, celery, performance, backend]
timestamp: 2026-08-30T17:30:00Z
---

# Aktueller Speichervertrag

Die folgende Begründung stammt aus der Einführung der Pyramiden. Die damaligen
Spalten `file_path`/`iiif_source_path` wurden durch relative `storage_key` und
`iiif_storage_key` ersetzt; lokale und S3-Speicherung nutzen denselben Key-Vertrag.
Pyramiden liegen neben dem geshardeten Master, nicht in einem flachen
MEDIA_ROOT. Aktueller Ablauf und Fehlerbehandlung:
[Media And IIIF](../../../almanac/architecture/workflows/media-and-iiif.md).
Die Aussage „kein Produktivsystem“ unten beschreibt ausschließlich den damaligen
Grund, keinen Backfill zu bauen, und ist keine heutige Betriebsbehauptung.


# Kontext

Issue #333: `generate_iiif_tiles` (`backend/src/katalon/workers/media_tasks.py`) hat
trotz des Namens nie eine Bildpyramide erzeugt — nur `info.json` abgerufen und ein
Manifest gebaut. Cantaloupes `Java2dProcessor` liest weiterhin aus der flachen
Originaldatei; ohne gekachelte Pyramide hat er keinen Random-Access in eine
bestimmte Auflösungsstufe, jede Tile-/Zoomstufen-Anfrage decodiert das komplette
Quellbild neu. Bei echten Archiv-Scans (TIFF, 50–200+ MP — der Normalfall für ein
GLAM-MMS) summiert sich das spürbar. Verwandtes, älteres Issue #309 stellte
dieselbe Frage bereits offen ("Original ersetzen oder behalten? Immer konvertieren
oder ab Schwellwert?").

# Entscheidung

**1. Immer konvertieren, kein Größen-Threshold.** Ursprünglich war ein Schwellwert
(>20MP) angedacht, um kleine Bilder von der Konvertierung auszunehmen. Verworfen:
`vips tiffsave --tile --pyramid` kostet bei kleinen Bildern nur wenige Millisekunden
und minimalen Storage-Overhead — ein Threshold wäre ein zusätzlicher Konfigurations-
Knopf ohne echten Nutzen (YAGNI).

**2. Original bleibt, Pyramide zusätzlich.** Neue nullable Spalte
`media_files.iiif_source_path`. `file_path` (Original) bleibt unverändert die
Quelle für Downloads; `iiif_source_path` zeigt auf `{file_id}_pyramid.tif` im
selben `MEDIA_ROOT`-Verzeichnis. Alle IIIF-Identifier-Stellen (Objekt-Manifest,
Medienliste-Thumbnail-Link, Portal-Thumbnail-Redirect, `fetch_image_info` im
Worker) lösen `iiif_source_path or file_path` auf — Cantaloupe bekommt die
Pyramide, wenn vorhanden, sonst fällt es auf den alten (langsamen) Pfad zurück.
Kosten: ca. 30–50 % zusätzlicher Storage-Bedarf pro Bild (Pyramide + Original statt
nur Original) — akzeptiert, weil ein separates Ersetzen des Originals eine
UX-Frage für Downloads aufwirft (Nutzer würde TIFF statt hochgeladenem
JPEG/PNG herunterladen), die hier nicht mitentschieden werden sollte.

**3. Kein Backfill für Bestandsdaten.** Zum Zeitpunkt der Entscheidung existiert
noch kein Produktivsystem mit echten Daten (frühe Beta-Phase) — eine nachträgliche
Batch-Konvertierung für Altdaten ist daher unnötige Komplexität für ein Problem,
das nicht existiert. Falls später doch Altdaten ohne Pyramide auftauchen (z. B.
nach einem Import-Skript, das an `_process()` vorbei schreibt), fallen sie einfach
auf den Original-Pfad zurück — funktional korrekt, nur ohne Performance-Vorteil.

**4. Fehlerbehandlung: Konvertierung ist best-effort, kein Upload-Abbruch.**
Schlägt `pyvips`/`libvips` fehl (fehlende Lib, korruptes Bild, unerwarteter
Fehler), loggt der Worker eine Warnung (`logger.warning(..., exc_info=True)`,
siehe [[broker-tolerant-enqueue]] zum Muster "Hintergrundfehler nicht stillschweigend
schlucken") und fällt auf das Original zurück. Der Media-Status wird dadurch
*nicht* auf `error` gesetzt — die Pyramide ist eine Performance-Optimierung, kein
Korrektheitskriterium für "ist die Datei nutzbar".

# Betroffene Stellen

- `backend/src/katalon/workers/media_tasks.py` — `_make_pyramid_tiff()`, Aufruf in `_process()`
- `backend/src/katalon/core/models.py` — `MediaFile.iiif_source_path`
- `backend/src/katalon/api/v1/media.py` — Thumbnail-Link, Thumbnail-Redirect, Löschen der Pyramide-Datei bei Media-Delete
- `backend/src/katalon/api/v1/objects.py` — Objekt-Manifest-Identifier
- `backend/src/katalon/workers/purge_tasks.py` — Pyramide-Datei bei Hard-Delete löschen
- `docker/Dockerfile.worker` — `libvips42t64` als Runtime-Dependency (Debian-Paketname, nicht `libvips42`)

Siehe auch [Medien-Multiformat](medien-multiformat.md) für den umgebenden
MIME-Kategorie-Dispatch, [Almanac: Media And IIIF](../../../almanac/architecture/workflows/media-and-iiif.md).
