---
title: "Configurable Portal Homepage Blocks"
summary: "The portal homepage renders an ordered list of admin-configured content blocks instead of a fixed featured/recent layout."
topics: [decisions, frontend, portal]
sources:
  - id: models
    type: file
    path: backend/src/katalon/core/models.py
  - id: portal-api
    type: file
    path: backend/src/katalon/api/v1/portal.py
  - id: portal-public-api
    type: file
    path: backend/src/katalon/api/v1/portal_public.py
  - id: settings-screen
    type: file
    path: frontend/admin/src/components/screens/ScreenSettings.tsx
  - id: home-page
    type: file
    path: frontend/portal/src/pages/HomePage.tsx
  - id: migration
    type: file
    path: backend/migrations/versions/0064_portal_config_homepage_blocks.py
  - id: decision-record
    type: file
    path: .agents/knowledge/decisions/configurable-portal-homepage.md
---

The authoritative rationale and decision status live in the OKF record
`.agents/knowledge/decisions/configurable-portal-homepage.md` [@decision-record]. This page summarizes the
choice and its implementation; update the OKF record first when changing the decision.


The portal homepage is built from `PortalConfig.homepage_blocks`, an ordered JSONB array of content blocks configured in the admin UI, instead of a fixed "featured objects then recent objects" layout hard-coded in `HomePage.tsx` [@models] [@home-page].


## Current Contract

`PortalConfig` gained one new JSONB column, `homepage_blocks`: an ordered list of blocks, each with `id`, `type`, `enabled`, and an optional multilingual `title` [@models]. Four block types exist:

- `text` — multilingual Markdown (`content: {de, en}`), rendered like static pages (`utils/markdown.ts`: `marked` + DOMPurify, class `prose`) with single line breaks kept, so blocks written as plain text keep their layout.
- `objects` — the most recent objects, count capped by `limit`.

Object cards in `objects`/`curated` show the same subtitle line as the search result list: the configured `subtitle_fields.object`, rendered with `renderFieldValue` (`utils/objectSubtitle.ts`); group fields and inherited facets are skipped, and without configuration the subtitle stays empty instead of printing raw metadata (earlier `creator`/`date` fallback showed `[object Object]` for group-typed dates).
- `curated` — reads the existing `featured_object_ids` field rather than introducing a second, parallel object list; only `limit` is block-specific.
- `collections` — `collections_mode` of `top` (root collections), `all`, `largest` (most public member objects, via `GET /portal/v1/collections?sort=largest`; counts only public objects so drafts don't inflate the ranking), or `selected` (explicit `collection_ids`), capped by `limit`. The admin picks `selected` collections through a search-and-add list (`settings/CollectionPicker.tsx`, ordered with up/down buttons) instead of typing UUIDs.

`curated` deliberately does not reuse the `WorkingSet`/"Arbeitsliste" model as a homepage source, even though issue #374 originally proposed it. Working sets are scoped to a user (`user_id`, optional `is_shared`) and built for personal/collaborative record collecting, not public curation — exposing one publicly on the homepage would require a new public read path and blur that scope. Since `PortalConfig.featured_object_ids` already exists and is already admin-editable for exactly this purpose, the `curated` block just displays it instead of duplicating the concept.

Validation happens in the shared Pydantic model `HomepageBlock`, used by both `PortalConfigRead` and `PortalConfigUpdate` in `portal.py`, so the single `GET/PUT /v1/portal/config` endpoint pair (already public-read / admin-write) needed no new routes [@portal-api]. The one exception is `collections_mode=top`: listing root-level collections needed a new `top_level` boolean query parameter on `GET /v1/collections`, since `parent_id=None` was already overloaded to mean "no filter" [@portal-public-api].

The admin UI adds a "Startseite" section next to the existing "Portal & Institution" settings, sharing its `PortalConfigRead` load/save round trip. Blocks are added, removed, reordered with up/down buttons (no drag-and-drop library — none was installed and the list sizes involved don't need one), and enabled/disabled per block [@settings-screen].

Existing installations get a one-time data migration seeding `homepage_blocks` with `[curated, objects]` (mirroring the previous hard-coded layout) so upgrading does not blank out anyone's homepage [@migration].

## Implementation Constraints

The homepage renderer in `HomePage.tsx` iterates `config.homepage_blocks`, dispatching to a small component per type; a block referencing a deleted collection or an emptied `featured_object_ids` list simply renders nothing rather than crashing the page [@home-page]. Adding a fifth block type (e.g. a saved-search or hero/CTA block, both mentioned as later ideas in #374) means adding one variant to `HomepageBlock` and one branch in the renderer and the admin editor — no schema migration required beyond the JSONB shape already in place.

Issue #373 (configurable portal terminology) landed after this feature and applies to it automatically for one block type: `collections`' default heading falls back to `t('nav.collections')`, which is terminology-aware, so an installation that renames `collection` to "Bestand" sees that name here too without further changes. The `curated` and `objects` blocks' default headings (`home.highlights` / `home.recent`) are generic phrases rather than record-type labels and are not wired into the terminology system — an admin who wants a different wording for those can already set a per-block title directly, which always takes precedence.
