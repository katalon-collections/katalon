---
title: "License and External Branding"
summary: "Katalon is licensed AGPL-3.0-or-later (SPDX headers on all source files); the software is presented externally as 'Katalon Collections' to distinguish it from the unrelated test-automation product at katalon.com, while code, packages, and internal docs keep the short name 'Katalon'."
topics: [decisions, operations, licensing, branding]
sources:
  - id: license
    type: file
    path: LICENSE
  - id: readme
    type: file
    path: README.md
  - id: about-screen
    type: file
    path: frontend/admin/src/components/screens/ScreenSettings.tsx
---

Katalon is licensed under the GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later) [@license]. Every source file under `backend/src`, `backend/tests`, `frontend/admin/src`, `frontend/portal/src`, and `e2e` carries an SPDX header (`SPDX-License-Identifier: AGPL-3.0-or-later` + `Copyright (c) 2026 Karl Krägelin`); new files should carry the same header.

## Context

CollectiveAccess, the closest comparable open-source GLAM collection-management system, is itself AGPL-3.0. A permissive license (MIT/Apache) would let anyone fork Katalon into a closed-source competing product or hosted service without giving anything back. AGPL's network-use clause closes that gap: anyone who runs a modified Katalon as a network service must publish their changes. It does not prevent commercial resale of unmodified Katalon itself — no OSI license does — but it does prevent a closed-source SaaS fork.

Separately, `katalon.com` is an unrelated commercial test-automation product with no connection to this project. To avoid confusion, the software presents itself externally as **"Katalon Collections"**.

## Decision

- License: AGPL-3.0-or-later, full text in [`LICENSE`](../../../LICENSE) [@license].
- `backend/pyproject.toml` and both `frontend/*/package.json` declare `"license": "AGPL-3.0-or-later"`.
- External branding: browser tab titles (`index.html` in both frontend apps), the Admin login screen, the README title, and the new "Über Katalon" / "About Katalon" settings tab (`ScreenSettings.tsx`, section `ueber`) all read **"Katalon Collections"** [@about-screen] [@readme].
- Internal/code-facing surfaces keep the short name **"Katalon"**: npm package names (`katalon-admin`, `katalon-portal`), the Python package (`katalon`), the GitHub repo (`karkraeg/Katalon`), Admin sidebar/breadcrumbs, and all internal docs (this almanac, `.agents/`, `CLAUDE.md`). No code identifiers, directory names, or config keys were renamed.

## Consequences

New user-visible strings that mention the product name should default to "Katalon Collections" if they're a first point of contact for an external user (browser title, login, about/marketing copy) and "Katalon" if they're internal chrome (navigation labels, admin breadcrumbs, log messages, code). New source files need the SPDX header pair shown above; there is no lint/CI check enforcing this yet, it's manual convention.
