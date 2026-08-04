---
title: "Broker Tolerant Enqueue"
summary: "Fire-and-forget Celery enqueue failures are logged and swallowed, while job-id endpoints report broker outages as 503."
topics: [decisions, operations, celery, resilience, backend]
sources:
  - id: decision-note
    type: file
    path: .agents/knowledge/decisions/broker-tolerant-enqueue.md
  - id: enqueue-helper
    type: file
    path: backend/src/katalon/workers/enqueue.py
  - id: enqueue-tests
    type: file
    path: backend/tests/test_enqueue.py
---

Katalon separates Celery enqueue calls by request semantics. Background work that is a side effect of an already successful HTTP write uses `enqueue()`, which logs broker failures and returns `None`; endpoints whose purpose is to start a pollable background job use `enqueue_or_503()`, which raises HTTP 503 when the broker is unavailable [@enqueue-helper]. The project recorded this decision after unguarded `.delay()` calls could turn completed writes into HTTP 500 responses during Redis outages [@decision-note].

## Context

The original incident came from request paths that committed primary database work and then called Celery `.delay()` for cleanup, tile generation, reindexing, or import follow-up work [@decision-note]. If Redis was unavailable, `.delay()` raised a broker connection error in the request path, so a user could receive a failed HTTP response even though the primary write had already happened [@decision-note].

That behavior conflicted with Katalon's operational posture for broker outages. The decision note states that Redis is intentionally not part of `/health` because a Celery broker outage should not mark ordinary read and write paths unhealthy [@decision-note]. The enqueue policy therefore had to distinguish optional background side effects from requests where the background job is the promised result.

## Decision

Use `enqueue(task, *args, **kwargs)` for fire-and-forget work. It calls `task.delay()`, returns the task id on success, logs a warning with exception info on any failure, and returns `None` instead of raising [@enqueue-helper]. The helper docstring names reindexing, tile generation, and relation cleanup as examples of work that must not break the triggering HTTP request [@enqueue-helper].

Use `enqueue_or_503(task, *args, **kwargs)` when the caller needs a task id. It also calls `task.delay()`, but on failure it logs a warning and raises `HTTPException(status_code=503)` with a broker-unavailable message [@enqueue-helper]. The helper docstring names media batch import and record import as paths where the broker is functionally required because the client polls the returned job id [@enqueue-helper].

## Consequences

Call sites must choose based on what the HTTP response promises. A completed write plus best-effort background work should not become a failed write because Redis is down; a request that claims a job was queued must not return success if there is no job id [@decision-note] [@enqueue-helper].

Tests pin both halves of the contract. `test_enqueue_returns_id_on_success` and `test_enqueue_swallows_broker_error` assert that fire-and-forget enqueue returns an id or `None` without raising [@enqueue-tests]. `test_enqueue_or_503_returns_id` and `test_enqueue_or_503_raises_503_on_broker_error` assert that job-id enqueue returns an id on success and raises HTTP 503 on broker failure [@enqueue-tests].

This decision constrains worker queue architecture and media workflows. For queue ownership, see [Celery And Worker Queues](../../architecture/backend/celery-and-worker-queues); for tile generation as an HTTP-triggered background effect, see [Media And IIIF](../../architecture/workflows/media-and-iiif).
