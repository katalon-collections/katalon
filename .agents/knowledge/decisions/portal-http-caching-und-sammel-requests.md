---
type: Decision
title: Kurze öffentliche HTTP-Caches und Sammel-Requests für Portal-Teaser
status: accepted
date: 2026-10-22
---

# Kontext

Portalseiten luden je verknüpftem Objekt zwei Requests (Datensatz, Vorschaubild); unter
paralleler Last bremste das API und DB.

# Entscheidung

`GET /portal/v1/objects/summaries` liefert sichtbare Objekte samt Vorschaubild gebündelt.
Anonyme Datensatz-, Medien-, Manifest-, Relations- und Suchfeld-Term-Reads senden
`Cache-Control: public, max-age=60`, mit `Vary: Authorization`, wo es eine Staff-Projektion
gibt; Staff erhält `private, no-store`. Dazu zwei Uvicorn-Prozesse
([API mit mehreren Workern](api-multiple-workers.md)).

# Begründung

60 Sekunden reichen gegen Lastspitzen und halten Sichtbarkeitsänderungen praktisch sofort.
`Vary` verhindert, dass ein Proxy die Staff-Sicht an Anonyme ausliefert.

# Citations

- `backend/src/katalon/api/v1/portal_public.py` (`_PUBLIC_CACHE`, `list_object_summaries`)
- `CHANGELOG.md` 1.45.0
