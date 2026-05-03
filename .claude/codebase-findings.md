# Katalon Codebase Findings

> Erstellt: 2026-05-03
> Branch: feat/issue-52-57-portal-basisfixes
> Ziel: Phase 8.0 – Portal-Basisfixes (#52–#57)

---

## Projektstruktur

```
backend/src/katalon/
  api/v1/           # FastAPI Router
  core/             # ORM models, schemas, dependencies
  integrations/     # ES, Cantaloupe, Authority adapters
  services/         # Business logic
  workers/          # Celery tasks
frontend/
  admin/            # Admin UI (React + Vite)
  portal/           # Public Portal (React + Vite)
```

---

## Backend APIs (Portal-relevant)

### Search (`/v1/search`) – backend/src/katalon/api/v1/search.py
- **GET** public, Parameter: `q`, `type`, `status`, `facets`, `page`, `page_size`, `meta_*`
- Returns: `SearchResponse` mit `total`, `page`, `page_size`, `items[]`, `facets{}`
- Items enthalten NUR: `id`, `record_type`, `title`, `status`, `score`
- **Problem:** Keine Thumbnails, keine Metadaten-Vorschau in Suchergebnissen
- Facetten: `by_type`, `by_status`, plus konfigurierbare `meta_<field>`
- `meta_*` Filter nutzen `.keyword` Subfields (implizit via dynamic mapping)

### Portal Config (`/v1/portal/config`) – backend/src/katalon/api/v1/portal.py
- **GET** public → `site_title`, `site_subtitle`, `hero_text`, `featured_object_ids`, `facet_fields`, `accent_color`, `logo_url`
- **PUT** auth-required (aber keine Admin-Rollen-Prüfung!)
- `_DEFAULTS` Dict fehlt `facet_fields` (wurde nachträglich via Migration 0007 hinzugefügt)

### Theme (`/v1/theme`) – backend/src/katalon/api/v1/theme.py
- **GET** public → Theme-Manifest JSON (CSS Tokens, Fonts, Logo, Favicon)
- File-basiert: `{media_root_parent}/themes/{theme_name}/theme.json`
- Kein PUT/Update-Endpoint

### Static Pages (`/v1/pages`) – backend/src/katalon/api/v1/pages.py
- **GET** `/v1/pages` → Liste published pages
- **GET** `/v1/pages/{slug}` → Einzelne published page
- **GET** `/v1/pages/admin` → Alle pages (auth)
- **POST/PUT/DELETE** → Auth-required
- `title` und `content` sind `dict` (JSONB) ohne Struktur-Validierung
- **Problem:** Keine Slug-Validierung (URL-safety), PUT könnte Duplicate Slugs erzeugen

### IIIF Manifest (`/v1/objects/{id}/iiif/manifest`) – backend/src/katalon/api/v1/objects.py:142-160
- Public, multi-canvas IIIF Presentation API 3.0
- Canvas width/height aus `media_file.iiif_manifest`
- **Problem:** Kein Status-Filter auf Parent-Object → Draft-Objekte liefern Manifest
- **Problem:** Filename als IIIF Identifier → Kollisionen möglich

### Objects CRUD – backend/src/katalon/api/v1/objects.py
- Standard CRUD + Media-Unterrouter
- `GET /v1/objects/{id}/media` → MediaFiles für Objekt
- `GET /v1/objects/{id}/media/{media_id}/file` → File-Download

### Entities, Places, Occurrences – jeweils eigene Router
- Analoge CRUD-Endpoints
- Keine speziellen Portal-Features

---

## Frontend Portal

### Routing (App.tsx)
```
/                    → HomePage
/search?q=...        → SearchPage
/objects/:id         → ObjectDetailPage
/entities/:id        → EntityDetailPage
/places/:id          → PlaceDetailPage
/page/:slug          → StaticPageView
```
**Fehlt:** `/occurrences/:id` Route!

### API Client (frontend/portal/src/api/client.ts)
- `BASE = import.meta.env.VITE_API_URL ?? ''`
- `api.objects.list/get/media`, `api.entities.get`, `api.places.get`
- `api.search.query` – nutzt `q`, `type`, `status`, `page`, `page_size`
- **Fehlt:** `api.occurrences` Client!
- **Fehlt:** Thumbnail-URLs in SearchResponse Interface

### HomePage (frontend/portal/src/pages/HomePage.tsx)
- Lädt Portal-Config, zeigt `site_title`, `hero_text`, `logo_url`
- Featured Objects (aus `featured_object_ids`)
- Neueste Zugänge (aus `api.objects.list({page_size: 12})`)
- **Problem:** Zeigt NUR Objekte, nicht Entities/Places/Occurrences
- **Problem:** Thumbnails sind leere `.thumb` Divs (nur CSS-Gradient)

### SearchPage (frontend/portal/src/pages/SearchPage.tsx)
- Lädt `facet_fields` aus Portal-Config
- Facetten-Panel: Typ, Status, konfigurierbare Meta-Facetten
- Suchergebnisse mit Pagination
- **Problem:** Result-Rows haben leere `.thumb-sm` (keine Thumbnails)
- **Problem:** Suchergebnisse zeigen nur `title` + `record_type` + `status`
- **Problem:** Keine Links für Occurrence-Detailseiten (nur object/entity/place)
- **Problem:** Navigation im Header hat keinen "Werke/Ereignisse" Link

### ObjectDetailPage (frontend/portal/src/pages/ObjectDetailPage.tsx)
- IIIF-Viewer via `@samvera/clover-iiif` (lazy-loaded)
- Fallback auf direktes Bild (`/v1/objects/{id}/media/{media_id}/file`)
- Metadaten-Anzeige mit `TYPE_LABEL_MAP` (hardcodierte deutsche Labels)
- **Problem:** `TYPE_LABEL_MAP` ist unvollständig (nur ~12 Felder)
- **Problem:** Extra-Metadaten zeigen Roh-Feldnamen statt Labels
- **Problem:** `@ts-expect-error` für `onError` Prop – Viewer-Version?

### EntityDetailPage (frontend/portal/src/pages/EntityDetailPage.tsx)
- Zeigt `entity_type` als Badge
- Lädt Relationen + verknüpfte Objekte
- Metadaten zeigen Roh-Feldnamen (kein Label-Mapping!)
- **Problem:** Keine Thumbnails für verknüpfte Objekte

### PlaceDetailPage (frontend/portal/src/pages/PlaceDetailPage.tsx)
- OpenStreetMap Embed (iframe)
- Lädt Relationen + verknüpfte Objekte
- Metadaten zeigen Roh-Feldnamen
- **Problem:** Keine Thumbnails für verknüpfte Objekte

### StaticPageView (frontend/portal/src/pages/StaticPageView.tsx)
- Lädt Seite via `api.pages.get(slug)`
- Zeigt `title` und `content` (beide JSONB dict, Sprache 'de')
- Funktioniert grundsätzlich

### Styles (frontend/portal/src/styles.css)
- CSS-Variablen für Theming: `--accent`, `--bg`, `--panel`, `--fg`, etc.
- Layout: `site-header`, `hero`, `obj-grid`, `search-layout`, `detail-layout`
- **Problem:** Keine responsive Breakpoints (Mobile!)
- **Problem:** `.page { padding: 40px 0 80px }` – kein horizontal padding auf kleinen Screens

### Theme-System
- `theme/loader.ts` → fetch `/v1/theme`, `applyTheme()`
- `theme/inject.ts` → CSS-Variablen + Fonts + Favicon + Title
- `theme/defaults.ts` → `DEFAULT_TOKENS` + `ThemeManifest` Interface

---

## Konkrete Issues & Fixes

### #52 – IIIF-Viewer einbetten
**Status:** Teilweise implementiert (Clover-IIIF in ObjectDetailPage)
**Probleme:**
- Viewer kann aufgrund von CORS/Netzwerk-Fehlern failen → `viewerError` state existiert, Fallback funktioniert
- Cantaloupe-Tiles sind laut IMPLEMENTIERUNGSPLAN noch nicht verdrahtet
- `@ts-expect-error` für `onError` Prop sollte geprüft werden

### #53 – Portal-Suche reparieren
**Status:** Suche funktioniert grundsätzlich, aber:
- Suchergebnisse haben keine Thumbnails
- Keine Metadaten-Vorschau (nur Titel + Typ + Status)
- Keine Occurrence-Detail-Links

### #54 – Alle 4 Primärtypen im Portal durchsuchbar + Detailseiten
**Status:**
- ✅ Objects: List + Detail
- ✅ Entities: Detail (keine Listenansicht)
- ✅ Places: Detail (keine Listenansicht)
- ❌ Occurrences: Weder Detail-Route noch API-Client!
- Header-Nav hat keinen Link für Occurrences

### #55 – Detailansicht: lokalisierte Labels statt Feldnamen
**Status:**
- ObjectDetailPage hat `TYPE_LABEL_MAP` (hardcodiert, unvollständig)
- EntityDetailPage + PlaceDetailPage zeigen ROHE Feldnamen
- **Lösung:** Labels aus `field_definitions` laden → `/v1/schema/fields?target_type=...`

### #56 – Globales Padding-Review im Portal
**Status:**
- `.container { padding: 0 24px }` – auf Mobile (375px) sind das nur ~20px nutzbar
- `.page { padding: 40px 0 80px }` – kein horizontal padding
- Keine Media Queries für <768px
- Detail-Layout: `grid-template-columns: 1fr 320px` – auf Mobile überlappend

### #57 – Statische Seiten-Route im Portal
**Status:** ✅ Implementiert (`/page/:slug` → StaticPageView)
- Footer lädt Pages dynamisch
- Funktioniert grundsätzlich

---

## Zusätzliche Probleme (nicht in Issues gelistet)

1. **Keine Occurrence-Route in App.tsx**
2. **Kein `api.occurrences` im Client**
3. **Admin-Rollen-Prüfung fehlt bei Portal-Config PUT**
4. **Keine Slug-Validierung bei Pages**
5. **IIIF Manifest für Draft-Objekte erreichbar**
6. **SearchResponse hat keine Thumbnail-URLs**
7. **Keine Tests für Portal-APIs** (search, portal, theme, iiif)
8. **Mobile-Responsiveness fehlt komplett**
9. **Clover-IIIF `@ts-expect-error` – Typings prüfen**

---

## Wichtige Dateien für Phase 8.0

| Datei | Zweck |
|-------|-------|
| `frontend/portal/src/App.tsx` | Routing, Header, Footer |
| `frontend/portal/src/api/client.ts` | API Client, TypeScript Interfaces |
| `frontend/portal/src/pages/SearchPage.tsx` | Suche + Facetten |
| `frontend/portal/src/pages/HomePage.tsx` | Startseite |
| `frontend/portal/src/pages/ObjectDetailPage.tsx` | Objekt-Detail + IIIF |
| `frontend/portal/src/pages/EntityDetailPage.tsx` | Entity-Detail |
| `frontend/portal/src/pages/PlaceDetailPage.tsx` | Place-Detail + Karte |
| `frontend/portal/src/pages/StaticPageView.tsx` | Statische Seiten |
| `frontend/portal/src/styles.css` | Alle Styles |
| `backend/src/katalon/api/v1/search.py` | Search Endpoint |
| `backend/src/katalon/api/v1/portal.py` | Portal Config |
| `backend/src/katalon/api/v1/theme.py` | Theme Endpoint |
| `backend/src/katalon/api/v1/pages.py` | Static Pages |
| `backend/src/katalon/api/v1/objects.py` | Objects + IIIF Manifest |
| `backend/src/katalon/services/search_service.py` | ES Search Logic |
