---
name: katalon-theming
description: >
  Theming, branding, and visual customization of Katalon Collections
  (the GLAM metadata management system, github.com/katalon-collections/katalon
  — unrelated to katalon.com). Covers the two theming layers: the Admin-UI
  "portal_config" quick-rebrand (accent color, logo, site text, a handful of
  color tokens, no restart) and the file-based drop-in theme package
  (theme.json + custom.css + custom.js + fonts, PORTAL_THEME env var,
  docker-compose mounts, nginx sub_filter injection, CSP constraints). Use
  when asked to theme, rebrand, restyle, whitelabel, or customize the Katalon
  portal's look; create or edit a theme.json/custom.css/custom.js under a
  themes/<name>/ directory; set or troubleshoot PORTAL_THEME; adjust portal
  accent color/logo/header colors via Admin settings; or diagnose why a
  Katalon theme isn't loading (CSP violations, missing nginx mount, stale
  PORTAL_THEME after edit). Do NOT use for unrelated Katalon backend/data
  work (schema, import, authority adapters) — see docs/04_anpassungen.md for
  those extension points instead.
license: MIT
---

# Katalon Theming

Katalon Collections' public **portal** is themeable through two independent,
stackable layers. Pick the layer that matches how deep the change is and
whether it needs to survive `docker compose pull`. The **admin app is not
themeable** by either layer — it stays fixed "Katalon Collections" branding
by design (see `license-and-branding` decision); don't try to reskin it
through this mechanism.

```
                    ┌─────────────────────────────┐
                    │ Layer 2: file-based theme    │  deploy-time, full control
                    │ themes/<name>/theme.json     │  (colors, fonts, CSS, JS)
                    │           custom.css/.js     │
                    └───────────────┬─────────────┘
                                    │ GET /v1/theme (public)
                                    ▼
                    portal loads on mount: loadAndApplyTheme()
                    sets CSS vars, injects <link> font/css, favicon
                                    │
                    ┌───────────────▼─────────────┐
                    │ Layer 1: Admin → Einstellungen│  live, DB-backed (portal_config)
                    │ accent_color, 4 color_tokens, │  no restart, applied ON TOP
                    │ logo, site_title/subtitle/    │  of layer 2 in App.tsx/HomePage.tsx
                    │ hero_text, sidebar position    │
                    └───────────────────────────────┘
```

## Layer 1 — Admin-UI quick rebrand (no file access, no restart)

Admin → Einstellungen (`frontend/admin/src/components/screens/ScreenSettings.tsx`)
writes to `PATCH /v1/portal/config` (admin role required), backed by the
`portal_config` DB table. Exposed fields:

- `site_title`, `site_subtitle`, `hero_text` — portal header/hero text.
- `accent_color` — sets CSS var `--accent`.
- `color_tokens` — a curated subset only: `--header-bg`, `--header-fg`,
  `--bg` (page background), `--panel`. There is **no raw token editor**;
  arbitrary CSS vars (`--fg`, `--border`, `--accent-50`, …) are not settable
  from this UI — use Layer 2 for those.
- `logo_url` — `POST /v1/portal/logo` file upload (jpg/png/svg/webp).
- `placeholder_image_url`, `detail_sidebar_position` (`left`/`right`),
  `browse_enabled_types`, `featured_object_ids`, `facet_sort` — layout/content
  knobs, not strictly visual theming but live in the same settings screen.

Applied client-side in `frontend/portal/src/App.tsx` (`useEffect` on mount,
after `loadAndApplyTheme()`) and in `HomePage.tsx` — `color_tokens` and
`accent_color` are written directly onto `document.documentElement.style`,
**overriding** whatever Layer 2's `theme.json` set for those same four vars.
Effect is instant for new page loads, no container restart, no file access.
Use this layer for: color accents, logo swap, header colors, site copy.
Not enough for: fonts, structural/layout CSS, footer rebuild, new fields.

## Layer 2 — File-based drop-in theme (deploy-time, full control)

### Directory layout

```
themes/<theme-name>/
├── theme.json       # manifest: tokens, fonts, logo, favicon
├── custom.css       # @font-face + full CSS overrides (loaded as <link>)
├── custom.js        # optional DOM enhancements, injected via nginx sub_filter
├── favicon.svg
└── fonts/*.woff2    # self-hosted, referenced from custom.css
```

Reference implementations in this repo: `themes/cvma-theme/`,
`themes/sidebar-theme/`.

### `theme.json` schema

```json
{
  "name": "My Theme",
  "version": "1.0.0",
  "tokens": {
    "--accent": "#000000", "--accent-50": "#f5f5f5", "--accent-100": "#e5e5e5", "--accent-ink": "#000000",
    "--bg": "#ffffff", "--panel": "#ffffff", "--panel-2": "#f7f7f7", "--border": "#c5c5c5",
    "--fg": "#000000", "--fg-2": "#464646", "--fg-3": "#828282", "--fg-4": "#a8a8a8",
    "--header-bg": "#ffffff", "--header-fg": "#000000"
  },
  "fonts": { "body": "/themes/<theme-name>/custom.css", "mono": null },
  "logo": null,
  "favicon": "<theme-name>/favicon.svg"
}
```

- `tokens` — full CSS custom-property set (see table below); merged over
  `DEFAULT_TOKENS` (`frontend/portal/src/theme/defaults.ts`), so omitted keys
  fall back to the built-in blue defaults, not empty.
- `fonts.body` — **convention override, not just a font stylesheet.**
  `applyTheme()` (`frontend/portal/src/theme/inject.ts`) injects it verbatim
  as `<link rel="stylesheet" href="{fonts.body}">`. Every real theme points
  this at its own `custom.css`, which then carries `@font-face` rules *and*
  arbitrary structural CSS — that's the only hook for anything beyond flat
  color tokens.
- `favicon` — path is prefixed with `/themes/` by `inject.ts`; give it
  relative to `themes/`, i.e. `"<theme-name>/favicon.svg"`, not just
  `"favicon.svg"`.
- `logo` — present in the schema but unused by `inject.ts` today; use Layer 1
  `logo_url` for an actual logo swap.

Token reference (all optional, defaults shown are the built-in blue theme):

| Token | Default | Used for |
|---|---|---|
| `--accent` | `#1e3a8a` | primary buttons, active nav underline, links |
| `--accent-50` / `--accent-100` | light tints | hover backgrounds, badges |
| `--accent-ink` | dark accent | text on tinted accent backgrounds |
| `--bg` | `#f4f5f7` | page background |
| `--panel` / `--panel-2` | white / off-white | cards, panels |
| `--border` | `#e4e6eb` | hairlines |
| `--fg`…`--fg-4` | dark→light gray scale | body text, muted text |
| `--header-bg` / `--header-fg` | navy / white | site header bar |

### Backend endpoint

`GET /v1/theme` (public, no auth) — `backend/src/katalon/api/v1/theme.py`.
Reads `settings.portal_theme` (env var `PORTAL_THEME`), resolves
`Path(MEDIA_ROOT).parent / "themes" / <PORTAL_THEME> / "theme.json"`, returns
its contents or a hardcoded fallback default if unset/missing.

`settings` is a `pydantic_settings.BaseSettings` singleton built once at
**process start** (`katalon/config.py`) — **changing `PORTAL_THEME` in `.env`
requires restarting the `api` container** (`docker compose up -d api`), it is
not hot-reloaded.

### Docker mounts (`docker-compose.override.yaml`)

```yaml
services:
  api:
    volumes:
      - ./themes:/var/lib/katalon/themes:ro   # sibling of MEDIA_ROOT — theme.py does .parent / "themes"
  portal:
    volumes:
      - ./themes:/usr/share/nginx/html/themes:ro   # static: custom.css/js, fonts, favicon
      - ./portal-nginx.conf:/etc/nginx/conf.d/default.conf:ro
```

The `api` mount target MUST be the sibling directory of wherever
`MEDIA_ROOT` resolves to inside that container (`/var/lib/katalon/media` by
default) — `theme.py` derives the themes path from `MEDIA_ROOT`'s *parent*,
it does not use a dedicated `THEMES_ROOT` setting.

### `portal-nginx.conf` — injecting `custom.js`

The portal is a prebuilt static SPA (no server-side templating), so
`custom.js` is injected by string substitution at the nginx layer:

```nginx
location / {
    sub_filter '</body>' '<script src="/themes/<theme-name>/custom.js" defer></script></body>';
    sub_filter_once on;
    try_files $uri $uri/ /index.html;
}
location /index.html {
    sub_filter '</body>' '<script src="/themes/<theme-name>/custom.js" defer></script></body>';
    sub_filter_once on;
    add_header Cache-Control "no-cache";
}
```

The theme name is **hardcoded in this file**, not derived from `PORTAL_THEME`
— when switching themes, update both `.env` (`PORTAL_THEME=`) and this
`sub_filter` path, then restart both `api` and `portal`. Skip this whole
block if the theme only needs `theme.json` + `custom.css` (no DOM scripting).

### `custom.css` conventions

- Self-hosted `@font-face` only — the main reverse-proxy's CSP
  (`nginx.conf`, applied at the outer/prod nginx, not `portal-nginx.conf`)
  sets `font-src 'self' data:` and `style-src 'self' 'unsafe-inline'`: no
  Google Fonts or other CDN `@import`/`<link>`. Ship `.woff2` files under
  `themes/<name>/fonts/`.
- React renders with inline/generated styles on several elements
  (`#root`, `main#main-content`) — expect to need `!important` to win against
  them, as `cvma-theme/custom.css` does.
- Target the portal's stable structural classes rather than guessing new
  ones: `.site-header`, `.site-header nav a`, `.site-header .logo`,
  `.hero`, `.hero-search`, `.obj-card`, `.facets`, `.detail-layout`,
  `.detail-main`, `.detail-meta`, `.site-footer`, `.footer-grid`,
  `.footer-col-title`, `.footer-links`. The header switches to its menu
  layout via `.site-header.is-compact` (set by `App.tsx` below 768 px *and*
  whenever logo, nav and actions overflow side by side), so style the opened
  menu as `.site-header.is-compact .header-actions.is-open`, not inside a
  width media query. Grep
  `frontend/portal/src/**/*.tsx` / `styles.css` for the exact class before
  inventing overrides — class names are the actual portal source, not part of
  a documented theming API, so verify against the checked-out frontend
  version.
- Group with a header comment block (see `cvma-theme/custom.css`) naming the
  visual reference/inspiration and font choices — keeps intent traceable.

### `custom.js` conventions

The portal is a client-routed React SPA — `custom.js` must survive route
changes without a full page reload:

```js
(function () {
  function run() { /* idempotent DOM work, e.g. rebuild footer, mark active nav */ }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', run)
  } else { run() }
  window.addEventListener('popstate', run)
  new MutationObserver(run).observe(document.body, { childList: true, subtree: true })
})()
```

Guard every DOM mutation for idempotency (e.g. `if (footer.querySelector('.footer-grid')) return`)
— the `MutationObserver` re-fires on every DOM write, including its own, so a
non-idempotent `run()` either loops or duplicates content.
`script-src 'self'` in the CSP forbids inline `<script>` and third-party
script tags — `custom.js` must be a same-origin file under `themes/<name>/`.

## Recipe: create a new drop-in theme

1. `mkdir -p themes/<name>/fonts`
2. Write `themes/<name>/theme.json` (tokens table above; point
   `fonts.body` at `/themes/<name>/custom.css`).
3. Write `themes/<name>/custom.css` — `@font-face` for self-hosted fonts,
   then structural overrides against the class list above.
4. Optional: `themes/<name>/custom.js` for DOM enhancements (footer,
   active-nav, anything the CSS-only layer can't reach).
5. Add `themes/<name>/favicon.svg`.
6. Set `PORTAL_THEME=<name>` in `.env`.
7. Ensure `compose.override.yaml` mounts `./themes` into both `api` and
   `portal` as shown above; if using `custom.js`, mount a `portal-nginx.conf`
   with the `sub_filter` pointed at `<name>`.
8. `docker compose up -d api portal` (or full restart) — `PORTAL_THEME` is
   read once at API process start.
9. Verify: `curl http://localhost:<port>/v1/theme` returns the new
   `theme.json`; open the portal, check Network tab for `200` on
   `/themes/<name>/custom.css` (and `custom.js` if used); check DevTools
   console for CSP violations (blocked font/script = wrong CSP or a
   non-self-hosted asset reference).

## Recipe: diagnose a theme not applying

- `/v1/theme` still returns the hardcoded defaults → `PORTAL_THEME` unset,
  typo'd, `api` container not restarted after `.env` edit, or `theme.json`
  missing at `{MEDIA_ROOT}/../themes/<name>/theme.json` inside the `api`
  container (check the volume mount target matches `MEDIA_ROOT`'s parent).
- Colors apply but fonts/structural CSS don't → `fonts.body` path wrong or
  `custom.css` not reachable at `/themes/<name>/custom.css` from the
  **portal** container (separate mount from the `api` one — both are
  required, for different reasons).
- `custom.js` never runs → confirm `portal-nginx.conf` is actually mounted
  over the portal's `default.conf` (not just present on the host) and the
  `sub_filter` theme-name path matches the active `PORTAL_THEME`.
- Admin-set colors (Layer 1) look like they "win" over `theme.json` — that's
  expected: `App.tsx`/`HomePage.tsx` apply `portal_config.color_tokens` and
  `accent_color` after `loadAndApplyTheme()`, intentionally layered on top.
- Browser console shows CSP `refused to load` → asset is not self-hosted
  under `/themes/<name>/`; the outer nginx CSP has no exception mechanism per
  theme, everything must be same-origin.

## Escalation: beyond CSS/JS theming

Layout restructuring that CSS can't express (e.g. left sidebar nav instead
of top nav, new routes/pages, removing/reordering sections) is not a
drop-in-theme concern — it's a source edit to `frontend/portal/src/`
(`App.tsx`, `styles.css`, `pages/`), documented in
`docs/04_anpassungen.md` §2 ("Portal-UI grundlegend umgestalten"), and
requires rebuilding/redeploying the `portal` image rather than mounting a
`themes/` directory. Confirm with the user before going there — it forks the
portal from upstream and loses the "pull new image, keep my theme" upgrade
path that Layers 1–2 preserve.
