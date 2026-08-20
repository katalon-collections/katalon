---
title: "Local Workflows"
summary: "How to choose and run Katalon's local development workflows without mixing compose stacks or backend interpreters."
topics: [development, operations, testing]
sources:
  - id: dev-doc
    type: file
    path: .agents/DEV.md
  - id: agent-rules
    type: file
    path: AGENTS.md
  - id: makefile
    type: file
    path: Makefile
  - id: dev-compose
    type: file
    path: docker-compose.dev.yml
  - id: backend-project
    type: file
    path: backend/pyproject.toml
---

Use this guide when starting Katalon locally or deciding which stack to use for a change. Katalon has three practical workflows: a Docker dev stack with live reload, a local Python and Node workflow backed by Docker services, and a production-like Docker stack for routing and build verification [@dev-doc]. The important outcome is not only that services start, but that backend commands run from `backend/`, frontend ports match the chosen stack, and later test work follows [Testing and Validation](testing-and-validation) instead of relying on a browser page load.

## Choose The Smallest Stack That Tests The Change

Use the Docker dev stack for ordinary full-stack feature work. It mounts backend source, migrations, and frontend source into containers, runs `uvicorn --reload` for the API, runs Vite for both frontends, and runs the Celery worker under `watchfiles` so it also reloads automatically on Python changes [@dev-doc] [@dev-compose].

Use the local workflow when debugger support or fastest feedback matters. In that mode, only `db`, `redis`, `elasticsearch`, and `cantaloupe` come from Docker, while the API, worker, Admin app, and Portal app run from separate terminals on the host [@dev-doc].

Use the production-like stack when checking nginx routing or built frontend assets. The repository documentation is explicit that this stack does not live-reload and should verify production build behavior rather than support active development [@dev-doc]. Its routing details are cross-cutting; use [Ports and Routing](../../reference/operations/ports-and-routing) when a browser URL is part of the task.

## Start The Docker Dev Stack

Build and start the dev stack from the repository root:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml build
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

After startup, run migrations in the API container:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec api alembic upgrade head
```

The dev override exposes the API on `8000`, Admin on `4000`, Portal on `4001`, database on `5432`, Redis on `6379`, Elasticsearch on `9200`, and Cantaloupe on `8182` [@dev-compose]. The Makefile has `make up-dev`, but that target starts only the infrastructure services `db`, `redis`, `elasticsearch`, and `cantaloupe`, so it is not a substitute for the full dev-compose command when the API or frontends must run in Docker [@makefile]. `make dev` is a shortcut for the two-flag `up --build` command above; `make test` and `make migrate` run `pytest` and `alembic upgrade head` inside the dev `api` container [@makefile].

## Run Locally Against Docker Services

For host-local backend work, create and activate the repository virtual environment, then install the backend package from `backend/` with dev extras:

```bash
uv venv
source .venv/bin/activate
cd backend
uv pip install -e ".[dev]"
```

Start backing services from the repository root:

```bash
docker compose up -d db redis elasticsearch cantaloupe
```

Run the application pieces in separate terminals:

```bash
cd backend
uvicorn katalon.main:app --reload --port 8000
```

```bash
cd backend
celery -A katalon.workers.celery_app worker --loglevel=info
```

```bash
cd frontend/admin
npm install
npm run dev
```

```bash
cd frontend/portal
npm install
npm run dev
```

The local Vite defaults documented for this workflow are Admin on `5173` and Portal on `5174`, with API docs at `8000/api/docs` [@dev-doc].

## Keep Backend Commands In `backend/`

Backend Python commands should run from `backend/`, not the repository root. The project rule exists because the repository root can contain another virtual environment, which has previously made backend tests use the wrong interpreter and miss dependencies such as `jinja2` [@agent-rules]. The backend package declares Python `>=3.12`, FastAPI, Celery, Elasticsearch, and its dev extras in `backend/pyproject.toml`, so that file is the package boundary for local installs and test commands [@backend-project].

## Verify The Workflow Before Coding

Check the URL that belongs to the chosen stack, then check `/health` or `/api/docs` before making code changes. If the task touches secrets, deployment variables, or public URLs, use [Environment and Secrets](../../reference/operations/environment-and-secrets) instead of copying local defaults into production paths.

When the workflow is running, move to [Testing and Validation](testing-and-validation). A running stack proves only that the process started; it does not prove the backend tests, frontend build, or Playwright flows pass.
