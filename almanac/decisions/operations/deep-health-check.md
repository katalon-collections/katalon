---
title: "Deep Health Check"
summary: "Katalon's `/health` endpoint is a Docker Compose readiness check for database, search, Redis-backed worker liveness, Cantaloupe, and optional Oxigraph, not a split liveness/readiness API."
topics: [decisions, operations, startup, resilience]
sources:
  - id: decision-note
    type: file
    path: .agents/knowledge/decisions/production-readiness-posture.md
  - id: app
    type: file
    path: backend/src/katalon/main.py
  - id: compose
    type: file
    path: docker-compose.yml
  - id: health-tests
    type: file
    path: backend/tests/test_health.py
  - id: health-tasks
    type: file
    path: backend/src/katalon/workers/health_tasks.py
  - id: decision-record
    type: file
    path: .agents/knowledge/decisions/production-readiness-posture.md
---

The authoritative rationale and decision status live in the OKF record
`.agents/knowledge/decisions/production-readiness-posture.md` [@decision-record]. This page summarizes the
choice and its implementation; update the OKF record first when changing the decision.


Katalon's `/health` endpoint is a deep readiness check for the production-like Docker Compose stack. It actively verifies PostgreSQL, Elasticsearch, Redis, a Celery Beat/Worker heartbeat, Cantaloupe, and Oxigraph when that integration is enabled; it returns HTTP 503 when any active check is degraded and is used by the API container healthcheck [@app] [@compose]. The project chose this single endpoint instead of a static OK response or a Kubernetes-style liveness/readiness split [@decision-note].

## Context

The production-readiness decision came from an operations audit that treated Katalon as a small-institution GLAM MMS rather than a high-scale multi-tenant service [@decision-note]. In that context, hiding database or search outages behind a static `{"status": "ok"}` response was more dangerous than adding a small dependency check to `/health` [@decision-note].

Docker Compose also shaped the boundary. The base Compose stack already uses service healthchecks and `depends_on: condition: service_healthy`, and the API service healthcheck calls `curl -sf http://localhost:8000/health` [@compose]. The decision therefore did not introduce separate liveness and readiness endpoints for a Kubernetes deployment model Katalon does not currently use [@decision-note].

## Decision

Keep `/health` as one readiness endpoint. The handler opens a database session, runs `SELECT 1`, pings Elasticsearch, reads Redis, records the default Celery queue backlog, checks the Beat/Worker heartbeat key, probes Cantaloupe's IIIF Image API root, and probes Oxigraph only when `settings.oxigraph_enabled` is true [@app]. It returns `{"status": "ok", "checks": ...}` only when every active check is `ok`; on any failed check it sets HTTP 503 and returns `{"status": "degraded", "checks": ...}` with the failing dependency named [@app].

The Redis portion is intentionally coarse. Celery Beat enqueues `katalon.heartbeat` every two minutes, and a worker refreshes the `katalon:beat:heartbeat` key with a ten-minute TTL. The worker also writes the key once on `worker_ready`, because Beat's first cron tick can be up to two minutes away and the API's Compose healthcheck (about 100 s) would otherwise fail on a fresh Redis, blocking the services that wait for `api` to be healthy; if the key is missing, `/health` reports a degraded `beat_heartbeat` without trying to distinguish Beat failure, worker failure, or Redis failure [@health-tasks] [@app]. The queue backlog and backup age remain informational fields outside `checks`, so they are visible to operators but do not gate the status code [@app].

## Consequences

Load balancers and Compose healthchecks can detect database, search, Redis, worker-heartbeat, Cantaloupe, and optional Oxigraph failures through one public health surface [@compose] [@app]. Tests pin the default endpoint shape by asserting `database`, `elasticsearch`, `redis`, `cantaloupe`, and `beat_heartbeat` checks, the informational fields, and the rule that HTTP status follows the aggregate check state [@health-tests].

The tradeoff is intentional coupling between API readiness and core dependency availability. If Elasticsearch or background-processing liveness is down, `/health` returns degraded even though some read/write API paths might still work [@app]. That matches the current operational posture: search, media delivery, and async work are core enough for Katalon's deployed service health, while detailed diagnosis still belongs in container logs and service-specific checks.
