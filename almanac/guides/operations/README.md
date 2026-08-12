---
title: "Operations"
summary: "Reading path for deploying, routing, backing up, and repairing Katalon without losing data."
topics: [operations, deployment, docker, database, safety]
sources:
  - id: agents
    type: file
    path: AGENTS.md
  - id: compose
    type: file
    path: docker-compose.yml
  - id: prod-compose
    type: file
    path: docker-compose.prod.yml
  - id: production-doc
    type: file
    path: docs/04_produktion.md
---

Use this operations hub when the task involves deployment, browser routing, backups, database incidents, or production-like verification. Katalon runs as a Docker Compose application with persistent PostgreSQL and Elasticsearch volumes, media mounts, frontend containers, an API service, workers, and an outer nginx route surface [@compose]. Production work adds `docker-compose.prod.yml`, TLS/nginx changes, manual migrations, first-run credential handling, and post-start health checks [@prod-compose] [@production-doc].

## Start With The Failure Surface

For local browser checks, read [Ports And Routing](../../reference/operations/ports-and-routing) before opening a URL. The normal production-like stack uses `http://localhost/admin/` for Admin and `http://localhost/` for Portal, while direct Admin and Portal container ports are debugging surfaces with different path behavior [@agents].

For production or production-like deploys, start with [Production Deployment](production-deployment), then use [Docker Compose Surfaces](../../reference/operations/docker-compose-surfaces) when compose files, service ports, mounts, or overrides are part of the change. If the work touches Admin build paths, nginx routing, or Vite base configuration, run [Admin Deploy Verification](admin-deploy-verification) before treating the deployment as done.

For secrets and startup gates, read [Environment And Secrets](../../reference/operations/environment-and-secrets). That page is the lookup surface for required environment variables, first-run admin behavior, production secret checks, and the test-only `KATALON_SECRETS_KEY` requirement.

## Protect Durable State

For backups, restore drills, or risky changes, use [Backup And Restore](backup-and-restore). PostgreSQL and media are the durable stores that must survive, while Elasticsearch can be rebuilt from stored records [@production-doc].

For database startup, credential, migration, or volume incidents, use [DB Problem Escalation](db-problem-escalation) first. The project rule is strict: inspect logs, understand the root cause, present options, and never delete or recreate database volumes or run `docker compose down -v` without Karl's explicit approval [@agents].

## Gotchas

[Known Gotchas](../../reference/operations/known-gotchas) is the compact preflight list for port confusion, Admin asset base paths, backend command location, the `click-didyoumean` lock pin, pytest secret setup, database volume safety, and code-level rebranding. Use it before broad testing, deployment, or repair work.
