---
title: "Known Gotchas"
summary: "Operational traps that should be checked before testing, deploying, or repairing the Katalon stack."
topics: [reference, operations, testing, deployment]
sources:
  - id: agents
    type: file
    path: AGENTS.md
  - id: gotcha-vite
    type: file
    path: .agents/knowledge/gotchas/vite-base-path.md
  - id: gotcha-click
    type: file
    path: .agents/knowledge/gotchas/click-didyoumean-lock.md
  - id: gotcha-secrets
    type: file
    path: .agents/knowledge/gotchas/pytest-secrets-key.md
---

Katalon's durable operational gotchas are mostly about choosing the right runtime surface before checking behavior: use the correct Compose port, preserve Admin's `/admin/` asset base path, run backend commands from `backend/`, keep the known `click-didyoumean` pin, provide `KATALON_SECRETS_KEY` for pytest, and never delete database volumes without explicit approval [@agents] [@gotcha-click] [@gotcha-secrets]. Use this page before following deployment, testing, or [database escalation](../../guides/operations/db-problem-escalation) work.

## Ports And Stack Choice

Root project instructions define the current port rule: `http://localhost/admin/` and `http://localhost/` are the normal production-like browser targets through the outer nginx on port `80`; direct `http://localhost:3000` and `http://localhost:3001` hit the Admin and Portal containers and are for container debugging only; `http://localhost:4000` and `http://localhost:4001` belong to the development Compose stack [@agents].

## Admin Asset Base Path

Admin's production image needs `VITE_BASE_PATH=/admin/` because the outer nginx routes Admin under `/admin/` [@agents]. If that build argument or adjacent nginx/Vite routing changes, Admin can build successfully while runtime JS and CSS paths point at `/assets/` and miss the Admin container [@agents] [@gotcha-vite].

Before changing `docker/Dockerfile.admin`, `docker/nginx.admin.conf`, or `frontend/admin/vite.config.ts`, check that `VITE_BASE_PATH` and nginx `location` blocks still match, then verify the deployed `/admin/` URL and its JS/CSS requests [@agents]. The operational verification lives in the Admin deploy guide.

## Backend Command Location

Backend Python commands should run from `backend/`, not the repository root, because the root also has a `.venv` and can select an interpreter that misses backend dependencies such as `jinja2` [@agents]. This applies to pytest, migrations, dependency syncs, and ad hoc backend commands.

## uv Lock Pin

The known `uv` dependency trap is `click-didyoumean`: the repository note records an inconsistent `backend/uv.lock` state where version `0.3.2` points at `click_didyoumean-0.3.1` files [@gotcha-click]. Keep `click-didyoumean==0.3.1` pinned until the lock condition is deliberately checked and fixed [@agents] [@gotcha-click].

## pytest Secrets Key

Backend pytest collection needs `KATALON_SECRETS_KEY`; without it, imports that instantiate settings can fail before any tests run [@gotcha-secrets]. The documented local command shape is:

```bash
cd backend
KATALON_SECRETS_KEY="test-katalon-secrets-key-32-chars" uv run pytest -q
```

The CI backend workflow sets the same environment variable globally, but local shells do not inherit that automatically [@gotcha-secrets].

## Database Volumes

Do not run `docker compose down -v`, delete database volumes, or recreate database storage as a repair shortcut without explicit approval [@agents]. The required sequence for database problems is to read container logs, identify the root cause, present options, and act only after approval [@agents].
