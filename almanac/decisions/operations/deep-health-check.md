---
title: "Deep Health Check"
summary: "Katalon's `/health` endpoint is a Docker Compose readiness check for database and Elasticsearch, not a split liveness/readiness API or a Redis broker check."
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
---

Katalon's `/health` endpoint is a deep readiness check for the production-like Docker Compose stack. It actively verifies PostgreSQL and Elasticsearch, returns HTTP 503 when either check is degraded, and is used by the API container healthcheck [@app] [@compose]. The project chose this single endpoint instead of a static OK response, a Kubernetes-style liveness/readiness split, or a Redis broker check [@decision-note].

## Context

The production-readiness decision came from an operations audit that treated Katalon as a small-institution GLAM MMS rather than a high-scale multi-tenant service [@decision-note]. In that context, hiding database or search outages behind a static `{"status": "ok"}` response was more dangerous than adding a small dependency check to `/health` [@decision-note].

Docker Compose also shaped the boundary. The base Compose stack already uses service healthchecks and `depends_on: condition: service_healthy`, and the API service healthcheck calls `curl -sf http://localhost:8000/health` [@compose]. The decision therefore did not introduce separate liveness and readiness endpoints for a Kubernetes deployment model Katalon does not currently use [@decision-note].

## Decision

Keep `/health` as one readiness endpoint. The handler opens a database session, runs `SELECT 1`, pings Elasticsearch, closes the Elasticsearch client, and returns `{"status": "ok", "checks": ...}` only when both checks are `ok` [@app]. On any failed check it sets HTTP 503 and returns `{"status": "degraded", "checks": ...}` with the failing dependency named [@app].

Do not include Redis in this endpoint. The decision note records that a Celery broker outage should not mark ordinary API read and write paths unhealthy [@decision-note]. Broker-dependent behavior is handled separately by the [Broker Tolerant Enqueue](broker-tolerant-enqueue) decision.

## Consequences

Load balancers and Compose healthchecks can detect database or Elasticsearch failures through one public health surface [@compose] [@app]. Tests pin the endpoint shape by asserting that the response reports exactly `database` and `elasticsearch` checks and that HTTP status follows the aggregate check state [@health-tests].

The tradeoff is intentional coupling between API readiness and search availability. If Elasticsearch is down, `/health` returns degraded even though some non-search API paths might still work [@app]. That matches the decision's operational posture: search is core enough for Katalon's deployed service health, while Redis-backed background work is not [@decision-note].
