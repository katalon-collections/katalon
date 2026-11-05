---
type: Architecture
title: System-Überblick
description: nginx → Portal/Admin (React) → FastAPI → Postgres/Redis/Elasticsearch → Celery → Cantaloupe. API-First, zwei getrennte Frontends.
tags: [architektur, services]
timestamp: 2026-07-09T00:00:00Z
---

# Einstieg

Katalon verwendet PostgreSQL als Primärspeicher, Elasticsearch als Suchprojektion
und optional Oxigraph als RDF-Projektion. Admin und Portal sind getrennte
React-Apps vor derselben FastAPI-Anwendung. Redis/Celery übernehmen Hintergrundarbeit;
Cantaloupe liefert IIIF-Bilder über den Medien-Autorisierungspfad.

Der aktuelle [Systemüberblick](../../../almanac/architecture/system/system-overview.md)
und die technische [Architekturanleitung](../../../docs/00_architektur.md)
beschreiben Routing, Dienste, Startup und Betrieb. Der [Tech-Stack](../decisions/tech-stack.md)
hält die Begründung fest. Exakte Images stehen in `release-meta.toml`.
