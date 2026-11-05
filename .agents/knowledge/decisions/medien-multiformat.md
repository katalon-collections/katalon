---
type: Decision
title: Medien-Multiformat — MIME-Kategorie-Dispatch statt Bild-only-Pipeline
description: Nicht-Bild-Dateien (PDF, Audio, Video, 3D) überspringen die Cantaloupe/IIIF-Pipeline und werden sofort ready; das Portal dispatcht den Viewer nach der MIME-Kategorie.
tags: [medien, iiif, portal, datenmodell]
timestamp: 2026-08-17T00:00:00Z
---

# Kontext

Die Medien-Pipeline war bild-only und an drei Stellen hart erzwungen:
MIME-Whitelist (JPEG/PNG/TIFF/WebP), Pillow-`verify()` in der API,
Frontend-`accept="image/*"`. Jede Canvas im Manifest war hart `"type":
"Image"` / `"format": "image/jpeg"`. Das Portal hatte keinen
Viewer-Dispatch — `IIIFViewer` rendert immer den Image-Viewer.

Geplant war das bereits in den Issues #123 (PDF), #125 (Viewer) und
#266 (Roadmap); alles bewusst „post-MVP" gelabelt.

# Entscheidung

- **MIME-Kategorie statt Bild-only.** `MediaFile.category` leitet sich
  aus dem MIME-Typ ab (`image`/`pdf`/`audio`/`video`/`3d`). Die
  Upload-Validierung akzeptiert zusätzlich PDF, MP3/WAV/OGG, MP4/WebM
  und GLB/GLTF (mit MIME-Fallback für `.glb`/`.gltf`, da Browser oft
  leeren Content-Type senden).
- **Nicht-Bild-Dateien überspringen Cantaloupe.** Kein IIIF-Tiling,
  `status` wird sofort `ready`, `_links.thumbnail` und IIIF-Manifest
  werden nur noch für Bilder erzeugt. **Kein Transcoding** — nur
  pre-encoded Dateien werden akzeptiert.
- **Viewer-Dispatch im Portal** nach `category`: Bild → Clover/IIIF,
  PDF → nativer Browser-Viewer, Audio/Video → HTML5-Player,
  3D → `@google/model-viewer` (lazy geladen, eigener Chunk).
- **Admin-Lightbox** lädt die auth-geschützte Datei als Blob und spielt
  sie als Object-URL ab (Video-Frame-Vorschau, kompaktes Audio,
  PDF-/3D-Icon).

# Begründung

Der gemeinsame Kern war nicht pro-Format-Arbeit, sondern der
**Manifest-Builder-Branch auf MIME-Kategorie** plus ein
**Frontend-Viewer-Dispatch** — beides einmalig umgestellt statt pro
Format neu. „Kein Transcoding" hält die Worker-Last minimal und deckt
den pragmatischen Fall (fertig encodierte Dateien) ab; echtes
Transcoding/Präsentationsderivate bleiben bewusst außerhalb des
MVP-Scope (Issue #127).

# Citations

[1] `backend/src/katalon/core/media_validation.py`
[2] `backend/src/katalon/api/v1/media.py`
[3] `backend/src/katalon/integrations/cantaloupe.py`
[4] `frontend/portal/src/components/MediaViewer.tsx`
[5] Issues #123, #125, #266
