---
type: Architecture
title: System-Überblick
description: nginx → Portal/Admin (React) → FastAPI → Postgres/Redis/Elasticsearch → Celery → Cantaloupe. API-First, zwei getrennte Frontends.
tags: [architektur, services]
timestamp: 2026-07-09T00:00:00Z
---

# Überblick

API-First: ein FastAPI-Backend liefert REST + OAI-PMH, zwei separate React-Apps
konsumieren es — Portal (public) und Admin (auth-geschützt).

```
nginx (TLS) → Portal / Admin (React)
            → FastAPI (Python 3.12) — /v1/* REST + OAI-PMH
                 → PostgreSQL + PostGIS
                 → Redis (Celery-Queue) → Celery Worker → Cantaloupe (IIIF)
                 → Elasticsearch 8 (Volltext, OAI-PMH-Quelle)
```

# Backend-Struktur

```
backend/src/katalon/
├── main.py              # FastAPI-App, Router, CORS, Startup
├── config.py             # Settings (Pydantic, aus .env)
├── database.py           # SQLAlchemy AsyncSession
├── core/                 # ORM-Modelle, Pydantic-Schemas, Dependencies
├── api/v1/                # HTTP-Handler (dünn: Routing + Validation)
├── services/              # Business-Logik
├── workers/               # Celery Tasks
├── integrations/           # ES, Cantaloupe, Authority-Adapter
└── management/             # CLI
```

Details, vollständige Service-Tabelle und Diagramm: `docs/00_architektur.md`.

# Citations

[1] `docs/00_architektur.md`
[2] Root `AGENTS.md`, Abschnitt "Monorepo-Struktur"
