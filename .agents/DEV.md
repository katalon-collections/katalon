# Katalon Development Setup

## Documentation and agent entry points

`AGENTS.md` defines the documentation ownership rules for every agent;
`CLAUDE.md` is a symlink to it. Start there before planning or changing code.
If present, read `.agents/maintainer/AGENTS.md` as explicitly required by the
root rules. That supplement holds private approvals, manual acceptance and
release operations; external contributors do not need it.
[CONTRIBUTING.md](../CONTRIBUTING.md) describes proposals, concepts and mockups.

- **Why:** [.agents/knowledge/decisions](knowledge/decisions/index.md) holds the
  authoritative decision records, including alternatives, rationale and status.
  OKF is the format of the whole `knowledge/` bundle, not another repository.
- **How the system works now:** [Almanac](../almanac/README.md) records runtime
  contracts, flows, architecture and pitfalls with source evidence. Its decision
  pages summarize the corresponding OKF record and document implementation.
- **How to work locally:** this file covers setup and tools; [docs/](../docs/00_architektur.md)
  contains detailed technical and operating guides. Concepts and dated audits
  describe proposals or past observations, not necessarily current behavior.
- **How to use the product:** the separate `katalon-collections/katalon-docs`
  repository contains the curator-facing documentation.

For a task, read its decision record and current Almanac contract. Record a new
architectural choice in OKF first, then update the affected Almanac pages and
technical guides. For an implementation-only change, update the behavior docs
without inventing a new decision. Link shared reasoning instead of maintaining
two versions. Remove fully superseded records and completed task plans; retain
relevant rationale and distinguish proposals from implemented features. Keep
documentation changes in Git history rather than a separate maintenance log. Current code establishes actual behavior; report a conflict with a
decision instead of silently changing the decision to match it.

CodeGraph, CodeAlmanac and the OKF renderer are optional; read Markdown and
check source files and local links directly when they are unavailable.
Run `codealmanac serve --host 127.0.0.1 --port 8765 --no-open` for the local wiki
at <http://127.0.0.1:8765/>; run `codealmanac validate` after wiki edits.
`make knowledge-site` renders OKF to `.agents/knowledge/_site/index.html`.
The OKF architecture/playbook/gotcha pages are short entry points or historical
notes; detailed current behavior belongs in Almanac and the technical guides.

The current curated export still excludes this file, the `.agents/` tree,
`almanac/`, and agent instruction files. Shared context is being prepared for
publication; `.agents/maintainer/` remains private even when shared context is
exported. The root `README.md` is the
internal entry point; the export replaces it with `README.public.md`.

Three development workflows are available. Choose based on what you need.

---

## 1. Docker Dev Stack (Recommended)

**Everything in Docker, but with live reload. No local Python or Node installation needed beyond Docker.**

Source code is mounted into the containers as volumes — saving a file reloads the process automatically. No image rebuild required for code changes.

```bash
cd /pfad/zum/katalon-checkout

# First time: build the dev images
docker compose -f docker-compose.yml -f docker-compose.dev.yml build

# Start everything (or: make dev)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

### What reloads automatically

| Service | Mechanism | Trigger |
|---|---|---|
| API (FastAPI) | `uvicorn --reload` | Any `.py` file change in `backend/src/` |
| Admin UI | Vite HMR | Any file change in `frontend/admin/src/` |
| Portal UI | Vite HMR | Any file change in `frontend/portal/src/` |
| Celery Worker | `watchfiles` | Any `.py` file change in `backend/src/` |

### Access

- **Admin UI**: <http://localhost:4000>
- **Portal UI**: <http://localhost:4001>
- **API** (direct, dev-only): <http://localhost:8000>
- **API Docs** (direct, dev-only): <http://localhost:8000/api/docs>

Port `8000` stays exposed only in the dev stack for direct API debugging. In the production-like stack the API is internal and reachable only via nginx at `/v1/`.

**Merksatz:** `4000/4001` gehören zum Dev-Compose-Stack. `3000/3001` gehören zum normalen/production-like Compose-Stack.

Optional: eigener Hostname mit echtem HTTPS (`https://katalon.local/`) via `make certs` (mkcert) — siehe `docs/dev_https.md`.

### Database migrations

The dev API runs `alembic upgrade head` before Uvicorn whenever its container starts. No separate migration command is required for the Docker dev stack.

---

### Windows via WSL 2

The Docker development stack is expected to run through Docker Desktop's Linux-container
backend with WSL 2; Katalon's images are Linux containers, not Windows containers. Keep
the checkout in the WSL filesystem and run Compose from its Linux shell so bind mounts and
file watching remain Linux-native. Set `MEDIA_ROOT=./media` and `BACKUP_ROOT=./backups`
for the project-local bind mounts rather than relying on the Linux host defaults
`/srv/katalon/...`.

This path is not yet verified on a Windows host. Native, non-Docker development and
production deployment on Windows are not documented or supported; use a Linux host for
production.

## 2. Local Development (Fastest feedback, more setup)

**Python and Node run directly on your machine. Requires uv and Node 20+.**

Useful when you want the absolute fastest feedback loop or need debugger support.

### Prerequisites

```bash
# Python env
cd /pfad/zum/katalon-checkout
uv venv
source .venv/bin/activate
cd backend && uv pip install -e ".[dev]" && cd ..
```

### Start backing services

```bash
docker compose up -d db redis elasticsearch cantaloupe
```

### Apply database migrations

```bash
cd backend
alembic upgrade head
```

Use Alembic for every empty or existing database. Do not create the schema through SQLAlchemy metadata and then stamp a revision: migration data, including the default permission matrix, would be skipped.

### Start the application (separate terminals)

```bash
# Terminal 1 — API
cd backend
uvicorn katalon.main:app --reload --port 8000

# Terminal 2 — Celery worker
cd backend
celery -A katalon.workers.celery_app worker --loglevel=info

# Terminal 3 — Admin UI
cd frontend/admin
npm install  # first time only
npm run dev

# Terminal 4 — Portal UI
cd frontend/portal
npm install  # first time only
npm run dev
```

### Access

- **Admin UI**: <http://localhost:5173>
- **Portal UI**: <http://localhost:5174>
- **API Docs**: <http://localhost:8000/api/docs>

---

## 3. Full Docker Stack (Production-like)

**For end-to-end testing, nginx routing, and verifying the production build.**

No live reload — requires image rebuild for code changes. Use this to verify the production build works, not for active development.

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
docker compose -f docker-compose.yml -f docker-compose.prod.yml up
```

- **Admin UI**: <http://localhost/admin/>
- **Portal UI**: <http://localhost/>
- **API**: proxied via nginx at <http://localhost/v1/>
- **API Docs**: proxied via nginx at <http://localhost/api/docs>

**Merksatz:** Für Browser-Checks ohne expliziten Dev-Hinweis zuerst `http://localhost/` und `http://localhost/admin/` verwenden. `3000/3001` sind nur interne Container-Ports. `4000/4001` sind Dev-Override-Ports.

---

## Common Tasks

### Run focused tests

Run checks for affected backend and frontend modules after changes. Record
visual and interaction checks for UI changes. The private maintainer supplement
reserves browser/UI and E2E acceptance for Karl in that checkout and the full
suite for a release gate. Always set a test
secrets key of at least 32 characters, including inside the dev container.

```bash
# Local, from backend/
KATALON_SECRETS_KEY="test-katalon-secrets-key-32-chars" uv run pytest tests/test_schema_service.py

# Docker dev stack
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec \
  -e KATALON_SECRETS_KEY="test-katalon-secrets-key-32-chars" \
  api uv run pytest tests/test_schema_service.py
```

### macOS: libvips bei lokalen Backend-Tests

Homebrew installiert libvips unter `/opt/homebrew/opt/vips/lib`. Lokale
Backend-Tests, die `pyvips` verwenden, deshalb direkt mit diesem Suchpfad
starten:

```bash
KATALON_SECRETS_KEY="test-katalon-secrets-key-32-chars" \
DYLD_LIBRARY_PATH="/opt/homebrew/opt/vips/lib" \
uv run pytest
```

Ohne `DYLD_LIBRARY_PATH` findet `pyvips` trotz installierter Homebrew-Formel
`libvips.42.dylib` nicht.

### Run stress tests (Locust)

Locust is included as a dev dependency. See `backend/tests/performance/README.md`
for the full command reference.

```bash
cd backend

# Against the local dev API (after `docker compose ... up`)
KATALON_LOCUST_EMAIL=admin@example.org \
KATALON_LOCUST_PASSWORD=<password> \
    uv run --extra dev locust -f tests/performance/locustfile.py

# Open http://localhost:8089 and start the swarm.
```

Headless smoke run (CI):

```bash
uv run --extra dev locust -f tests/performance/locustfile.py \
    --headless -u 10 -r 2 -t 60s \
    --host http://localhost:8000 \
    --html /tmp/locust-report.html
```

### Run a DAST scan locally (OWASP ZAP)

`.github/workflows/dast-staging.yml` only ever runs on a schedule against
the staging URL secret — it needs no GitHub Actions run to try locally.
ZAP's full scan (spider + active attack payloads) can point at the local
dev stack directly, no tunnel needed, since both run on the same machine:

```bash
# Against the dev stack's outer nginx (docker-compose.dev.yml up first)
docker run --rm -v "$(pwd)":/zap/wrk/:rw ghcr.io/zaproxy/zaproxy:stable \
    zap-full-scan.py -t http://host.docker.internal:4001 \
    -r /zap/wrk/zap-report.html

# Admin instead of Portal:
docker run --rm -v "$(pwd)":/zap/wrk/:rw ghcr.io/zaproxy/zaproxy:stable \
    zap-full-scan.py -t http://host.docker.internal:4000 \
    -r /zap/wrk/zap-report.html
```

`host.docker.internal` resolves to the host from inside the ZAP container
on Docker Desktop/OrbStack; on plain Linux Docker use `--network host` and
target `http://localhost:<port>` instead. This is an **active** scan — it
sends real SQLi/XSS/fuzzing payloads and can create or corrupt records, so
only ever point it at the dev stack's synthetic data, never at a database
you care about. It answers "are there injection/XSS/header issues", not
"can the wrong role reach admin" — that authorization-boundary question is
covered deterministically by
`backend/tests/test_route_security_boundaries.py` instead, which runs on
every push as part of the normal test suite.

### Reset local database (dev stack)

After resetting the database, start the API; its entrypoint applies all migrations before Uvicorn starts:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d db api
```

See `dev_reset.md` for a full reset including Elasticsearch.

### Rebuild a single service after Dockerfile change

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml build api
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d api
```

### Reload Celery worker after worker code change

The dev worker uses `watchfiles`, so code changes in `backend/src/` reload automatically. If you need a manual restart:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml restart worker
```

### Tail logs

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f api
docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f worker
```

### Shell into a container

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec api bash
```
