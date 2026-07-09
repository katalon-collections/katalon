---
type: Decision
title: Fixierte Tech-Stack-Entscheidungen
description: Backend/DB/Suche/Bildserver/Queue/Frontend/Deployment als Paket am Projektstart festgelegt, seither nicht revidiert.
tags: [tech-stack, infrastruktur]
timestamp: 2026-07-09T00:00:00Z
---

# Kontext

Katalon ist ein Python/React-Rewrite von CollectiveAccess (PHP-Monolith,
XML-Konfiguration, keine saubere API, keine Python/Datenscience-
Integration). Der Stack wurde als zusammenhängendes Paket am
Projektstart entschieden, nicht Komponente für Komponente einzeln
debattiert.

# Entscheidung

| Komponente     | Wahl                                       |
|-----------------|---------------------------------------------|
| Backend         | Python 3.12+ / FastAPI                      |
| Datenbank       | PostgreSQL 16 + PostGIS + JSONB             |
| Suche           | Elasticsearch 8.x                           |
| Bildserver      | Cantaloupe (IIIF Image API 3)               |
| Task Queue      | Celery + Redis                              |
| Frontend        | React + TypeScript (Vite) — zwei separate Apps (Admin, Portal) |
| Deployment      | Docker Compose                              |
| IIIF im MVP     | Ja, von Anfang an                           |

# Begründung

- **PostGIS**: Place-Typ braucht geografische Queries nativ, kein
  generisches Attribut-System dafür nötig (vgl.
  [Vier Bestandstypen](vier-bestandstypen.md)).
- **JSONB statt EAV-Tabellen**: dynamische Metadaten pro Typ ohne
  Schema-Migrations-Zwang bei jedem neuen Feld.
- **Zwei getrennte Frontend-Apps** statt einer: Admin (auth-geschützt,
  Dateneingabe) und Portal (public, Suche/IIIF-Viewer) haben
  unterschiedliche Zielgruppen, Auth-Anforderungen und Deploy-Zyklen.
- **Docker Compose statt Kubernetes o.ä.**: Zielgruppe sind GLAM-
  Institutionen ohne eigenes Ops-Team; ein `docker compose up` muss
  reichen.
- **IIIF nicht Post-MVP**: Bildpräsentation ist Kernfunktion für GLAM,
  kein Nice-to-have.

# Citations

[1] Root `CLAUDE.md`, Abschnitt "Fixierte Architekturentscheidungen"
[2] `KONZEPT.md`, Datenmodell-Abschnitt
