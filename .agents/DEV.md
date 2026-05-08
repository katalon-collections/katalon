# Katalon Development Setup

Two development workflows are available:

## 1. Local Development (Recommended for rapid iteration)

**Fastest feedback loops. Code changes reload instantly.**

### Prerequisites

```bash
# Create venv
cd /Users/karl/Coding/Katalon
uv venv

# Activate
source .venv/bin/activate
```

### Start Services

Terminal 1 - Database:

```bash
docker compose up -d db
```

Terminal 2 - Python API (auto-reloads):

```bash
cd /Users/karl/Coding/Katalon/backend
uvicorn katalon.main:app --reload --port 8000
```

Terminal 3 - Admin Frontend (hot-reload):

```bash
cd /Users/karl/Coding/Katalon/frontend/admin
npm install  # first time only
npm run dev
```

### Access

- **Admin UI**: <http://localhost:5173>
- **API Docs**: <http://localhost:8000/api/docs>
- **API Health**: <http://localhost:8000/health>

---

## 2. Full Docker Compose Stack

**For production-like testing, end-to-end validation.**

### Start Everything

```bash
cd /Users/karl/Coding/Katalon
docker compose down  # clean first time
docker compose build --no-cache
docker compose up
```

### Access

- **Admin UI**: <http://localhost:3000>
- **Portal UI**: <http://localhost:3001>
- **API Docs**: <http://localhost:8000/api/docs>
- **Nginx**: <http://localhost>

### Services Included

- PostgreSQL 16 + PostGIS
- Redis 7
- Elasticsearch 8.13
- Cantaloupe IIIF Server
- FastAPI Backend
- Celery Worker
- Admin React App
- Portal React App
- Nginx Reverse Proxy

---

## Switching Between Modes

**To switch from local to Docker:**

```bash
docker compose up -d db redis elasticsearch cantaloupe
# Kill local terminals, then restart with docker compose
docker compose up
```

**To switch from Docker to local:**

```bash
docker compose down
# Kill docker, restart local terminal servers
```

---

## Common Tasks

### Run Tests Locally

```bash
cd /Users/karl/Coding/Katalon/backend
source ../.venv/bin/activate
pytest tests/
```

### Database Migrations (Alembic)

```bash
cd /Users/karl/Coding/Katalon/backend
alembic upgrade head
```

### Reset Local Database

```bash
docker compose down db
docker volume rm katalon_db_data
docker compose up -d db
```

### View API Logs (Docker)

```bash
docker logs katalon-api-1 -f
```

### Shell into Container

```bash
docker exec -it katalon-api-1 /bin/bash
```
