# Katalon Development Setup

Three development workflows are available. Choose based on what you need.

---

## 1. Docker Dev Stack (Recommended)

**Everything in Docker, but with live reload. No local Python or Node installation needed beyond Docker.**

Source code is mounted into the containers as volumes — saving a file reloads the process automatically. No image rebuild required for code changes.

```bash
cd /Users/karl/Coding/Katalon

# First time: build the dev images
docker compose -f docker-compose.yml -f docker-compose.dev.yml build

# Start everything
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

### What reloads automatically

| Service | Mechanism | Trigger |
|---|---|---|
| API (FastAPI) | `uvicorn --reload` | Any `.py` file change in `backend/src/` |
| Admin UI | Vite HMR | Any file change in `frontend/admin/src/` |
| Portal UI | Vite HMR | Any file change in `frontend/portal/src/` |
| Celery Worker | **Manual** | `docker compose restart worker` |

### Access

- **Admin UI**: <http://localhost:3000>
- **Portal UI**: <http://localhost:3001>
- **API**: <http://localhost:8000>
- **API Docs**: <http://localhost:8000/api/docs>

**Merksatz:** `3000/3001` gehören zum normalen/production-like Compose-Stack. `4000/4001` gehören nur zum Dev-Compose-Stack weiter unten.

### Run migrations after startup

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec api alembic upgrade head
```

---

## 2. Local Development (Fastest feedback, more setup)

**Python and Node run directly on your machine. Requires uv and Node 20+.**

Useful when you want the absolute fastest feedback loop or need debugger support.

### Prerequisites

```bash
# Python env
cd /Users/karl/Coding/Katalon
uv venv
source .venv/bin/activate
cd backend && uv pip install -e ".[dev]" && cd ..
```

### Start backing services

```bash
docker compose up -d db redis elasticsearch cantaloupe
```

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

- **Admin UI**: <http://localhost:3000>
- **Portal UI**: <http://localhost:3001>
- **API**: proxied via nginx at <http://localhost>

**Merksatz:** Für Browser-Checks ohne expliziten Dev-Hinweis zuerst `3000/3001` probieren. `4000/4001` sind kein allgemeiner Standard-Port, sondern nur Dev-Override.

---

## Common Tasks

### Run tests

```bash
# Local
cd backend && pytest tests/

# Docker dev stack
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec api pytest tests/
```

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

```bash
# Local
cd backend && alembic upgrade head

# Docker dev stack
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec api alembic upgrade head
```

### Reset local database (dev stack)

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml down
docker volume rm katalon_db_data
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d db
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec api alembic upgrade head
```

See `dev_reset.md` for a full reset including Elasticsearch.

### Rebuild a single service after Dockerfile change

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml build api
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d api
```

### Reload Celery worker after worker code change

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
