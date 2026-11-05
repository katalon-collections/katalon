---
type: Decision
title: Medien-Sichtbarkeit (is_public) und nginx auth_request vor Cantaloupe
description: MediaFile.is_public erlaubt, einzelne Bilder eines sonst öffentlichen Objekts vom Portal zu verbergen; da Cantaloupe selbst keine Auth kennt, gated ein neuer nginx auth_request-Block jede /iiif/-Anfrage gegen einen schlanken Backend-Endpoint statt Cantaloupe hinter einem eigenen Auth-Layer zu verstecken.
tags: [media, iiif, cantaloupe, nginx, security, backend, admin]
timestamp: 2026-08-31T10:15:00Z
---

# Kontext

Anforderung: Medien nicht-öffentlich schalten können — Metadaten eines Objekts
bleiben im Portal sichtbar, einzelne Bilder aber nicht. Bisher gab es nur die
Record-`status`-Gate (`draft`/`public`/…, siehe `core/visibility.py`), keine
Sichtbarkeit auf Medien-Ebene.

Beim Umsetzen zeigte sich ein bestehendes Sicherheitsloch: Cantaloupe (IIIF-
Bildserver) hat keine eigene Auth. Das äußere nginx (`docker/nginx.conf`)
proxyte `/iiif/` bisher ungeprüft durch — jeder mit bekanntem/erratbarem
Dateinamen konnte Bilder auch zu Draft-Objekten direkt von Cantaloupe laden,
unabhängig vom Record-`status`. Der neue `is_public`-Schalter wäre ohne Fix
dieser Lücke wirkungslos gewesen.

# Entscheidung

**1. `MediaFile.is_public: bool` (default `true`), Migration 0048.** Kein
Record-weites Feld — Sichtbarkeit ist pro Datei, weil ein Objekt teils
öffentliche, teils sensible Aufnahmen haben kann (z. B. Vorder-/Rückseite mit
Provenienzvermerk). PATCH über bestehenden `MediaPatch`/`patch_media`
(admin/editor only), analog zu `is_primary`.

**2. Cantaloupe bleibt unverändert — Gate via nginx `auth_request`.**
Alternative wäre signierte/zeitbegrenzte URLs gewesen (siehe Aufwandsschätzung
in der Session: ~1 Tag, Token-Ablauf kollidiert mit IIIF-Viewer-Caching).
Stattdessen: natives nginx-Feature `auth_request` vor der `/iiif/`-Location,
das für jede Anfrage einen internen Subrequest an einen neuen, schlanken
Backend-Endpoint (`GET /v1/media/_authorize`, `internal_router` in
`api/v1/media.py`) schickt. Der Endpoint least den Original-Pfad aus
`X-Original-URI`, löst den IIIF-Identifier auf `MediaFile` auf und prüft
`ensure_publicly_visible(obj, current_user, …)` + `is_public`. 200 = Cantaloupe
liefert aus, 403 = nginx blockt, bevor die Anfrage Cantaloupe erreicht.

**3. Eigener Router ohne globale Auth-Pflicht.** `main.py` hängt an alle
Router `dependencies=_authenticated` (= `get_current_user`, wirft 401 ohne
Token) — das hätte `_authorize` für anonyme Portal-Besucher komplett blockiert.
Deshalb eigener `media.internal_router`, in `main.py` **ohne**
`dependencies=_authenticated` eingehängt; der Endpoint nutzt intern
`OptionalCurrentUser`, genau wie die bestehenden `/portal/v1/…`-Endpoints.

**4. Admin-Thumbnails: Redirect-Ziel host-relativ statt `public_iiif_base()`.**
Der bestehende Thumbnail-Redirect-Endpoint (`serve_media_thumbnail`) leitete
bisher auf die absolute `CANTALOUPE_PUBLIC_URL` um. Lokal ist die auf
`http://` gesetzt, während die Seite selbst unter `https://localhost` läuft —
ein Schemawechsel gilt für `fetch()` als Cross-Origin, wodurch der Browser den
`Authorization`-Header beim Redirect fallen lässt. Ergebnis: eingeloggte
Admin-User hätten private/Draft-Thumbnails nicht mehr laden können. Fix:
Redirect-Ziel ist jetzt `/iiif/3/{id}/…` (host-relativ), dadurch bleibt der
Redirect in jeder Umgebung same-origin und der Header wird mitgeschickt.
Betrifft nur den Redirect-Endpoint; das IIIF-Presentation-Manifest
(`objects.py:iiif_manifest`, nur für öffentliche Objekte erreichbar) behält
absolute Cantaloupe-URLs, weil dessen Konsument (OpenSeadragon/Clover IIIF im
Portal) sie ohnehin ohne Auth lädt.

**5. Admin-Grid nutzt jetzt authentifizierten Blob-Fetch statt `<img src>`.**
`ScreenForm.tsx` zeigte Thumbnails bisher per rohem `<img src={cantaloupeUrl}>`
— genau die Lücke aus Punkt 2/Grund, warum das überhaupt funktionierte, ohne
dass die Backend-Auth-Prüfung je durchlaufen wurde. Neue `ImageThumb`-
Komponente (Pattern von der bereits vorhandenen `VideoThumb` übernommen) holt
das Thumbnail per `authorizedFetch` + Blob-URL, damit der Bearer-Token
mitgeschickt wird — ein `<img>`-Tag kann das nicht.

# Betroffene Stellen

- `backend/src/katalon/core/models.py` — `MediaFile.is_public`
- `backend/migrations/versions/0048_add_is_public_to_media_files.py`
- `backend/src/katalon/api/v1/media.py` — `MediaPatch.is_public`, Anon-Filter in `list_media`/`serve_media_file`/`serve_media_thumbnail`, neuer `internal_router`/`authorize_media`, host-relativer Thumbnail-Redirect
- `backend/src/katalon/api/v1/objects.py` — `iiif_manifest` filtert `is_public` bei Media-Auswahl
- `backend/src/katalon/main.py` — `media.internal_router` ohne `_authenticated`
- `docker/nginx.conf` — `auth_request` vor `/iiif/`, interne `/internal/media-authorize`-Location
- `frontend/admin/src/components/screens/ScreenForm.tsx` — `ImageThumb`, Sichtbarkeits-Toggle im Medien-Grid
- `frontend/admin/src/api/client.ts` — `MediaFile.is_public`, `media.patch`-Signatur

Nicht angefasst: `docker-compose.dev.yml` exponiert Cantaloupe weiterhin direkt
auf Port 8182 (lokaler Dev-Stack, kein nginx-Gate) — akzeptiertes Risiko, da
nur auf dem Entwicklerrechner erreichbar.

Doku-Lücke: Es existiert bisher keine Nutzer-Doku-Seite zu Medien-Verwaltung
in `docs/` (nur Schema- und CSV-Import-Anleitung) — die neue
Sichtbarkeits-Option ist dort daher (noch) nicht dokumentiert.
