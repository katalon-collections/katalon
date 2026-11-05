---
type: Decision
title: Fixierte Tech-Stack-Entscheidungen
description: Backend/DB/Suche/Bildserver/Queue/Frontend/Deployment als Paket am Projektstart festgelegt; Python-Version im September 2026 von 3.12 auf 3.14 angehoben.
tags: [tech-stack, infrastruktur]
timestamp: 2026-07-09T00:00:00Z
---

# Kontext

Katalon braucht dynamische Schema-Konfiguration über eine Oberfläche,
eine saubere REST-API und Python/Datenscience-Integration. Der Stack
wurde als zusammenhängendes Paket am Projektstart entschieden, nicht
Komponente für Komponente einzeln debattiert.

# Entscheidung

| Komponente     | Wahl                                       |
|-----------------|---------------------------------------------|
| Backend         | Python 3.14+ / FastAPI                      |
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
- **Python 3.12 → 3.14 (September 2026)**: Das Projekt startete im April 2026 mit Python 3.12.
  Vor der Umstellung auf 3.14 wurden die Abhängigkeiten und der Build geprüft: alle Backend-Dependencies lösen
  unter 3.14 zu vorgebauten Wheels auf, Docker-Basis-Image (`python:3.14-slim`)
  ist wie 3.12 auf Debian trixie gebaut (`libvips42t64` bleibt gültig), und
  die volle Backend-Testsuite verhält sich unter 3.12 und 3.14 identisch
  (1008/1011, ein vorbestehender Event-Loop-Flake in
  `test_search_visibility.py` bei Volllauf, kein 3.14-spezifisches Problem).

# Citations

[1] Root `CLAUDE.md`, Abschnitt "Fixierte Architekturentscheidungen"
[2] `KONZEPT.md`, Datenmodell-Abschnitt
