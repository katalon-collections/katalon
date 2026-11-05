---
type: Decision
title: Subsystem-Erweiterungen (RDF/Oxigraph/SPARQL) — First-Party-Modul als optionale First-Party-Integration
description: Querschneidende Subsysteme wie Oxigraph-Triple-Store und SPARQL-Endpoint werden als First-Party-Module mit Feature-Flags und Docker-Compose-Profilen umgesetzt; ein dynamisches Plugin-System liegt außerhalb des derzeit benötigten Umfangs.
tags: [architektur, platform, rdf, oxigraph, sparql, plugins, yagni]
timestamp: 2026-09-07T12:00:00+02:00
---

# Kontext

Für die geplante Linked-Data-Erweiterung (Issues #364 Oxigraph-Projektion, #358 SPARQL-Endpoint, #359 RDF-Vertragstests/SHACL) kam die Frage auf, ob für solche großen, optionalen Erweiterungen ein generisches Plugin-System / eine installierbare Plugin-Lifecycle-Architektur gebaut werden sollte.

Katalon besitzt bereits zwei schlanke Anpassungs- und Erweiterungsmechanismen:
- Schmale Strategy-Adapter mit Registry (`AuthoritySource`, `MetadataFormat`, `SourceFormat`) für reine Input/Output-Transformationen ohne Hintergrunddienste oder Persistenzänderungen.
- Deployment-Anpassungen über Compose-Overrides (`docker-compose.override.yml`) und Themes (`theme.json` + CSS-Mounts).

# Entscheidung

**Keine generische Plugin-Architektur für Subsystem-Erweiterungen.**

Große Erweiterungen wie Oxigraph und SPARQL werden als reguläre, optionale First-Party-Module im Core-Monorepo implementiert und über Feature-Flags und Compose-Profile gesteuert:

1. **Subsysteme sind keine Plugins:**
   Oxigraph/SPARQL schneidet quer durch alle Schichten: eigener Daemon-Container mit persistentem Volume, Celery-Sync-Tasks an Save/Delete/Publish-Hooks, FastAPI-Router mit Auth und Rate-Limiting, Admin-UI-Observability (Lag, Rebuild) und Pydantic-Settings. Eine dynamische Plugin-Schicht müsste diese Andockpunkte zusätzlich absichern und versionieren. Für die vorhandene Integration wird diese zusätzliche Schnittstelle nicht benötigt.
2. **Vorbild im Core:**
   Elasticsearch (Suchindexierung, Health, Celery-Reconciliation) und Cantaloupe (IIIF-Derivate, Auth-Gate, Pyramiden-Generierung) sind ebenfalls First-Party-Integrationen und keine Plugins. Oxigraph folgt exakt diesem Vorbild als materialisierte Read-Projektion (CQRS) neben Postgres.
3. **Opt-in ohne Overhead:**
   - **Code:** Fest im Repo (`katalon.integrations.oxigraph`, `katalon.services.rdf_sync_service`, `katalon.api.v1.sparql`), voll typprüfbar und CI-getestet.
   - **Feature-Flag:** `OXIGRAPH_ENABLED=false` (Default). Wenn deaktiviert, brechen Celery-Tasks sofort per `return` ab (no-op), SPARQL-Routen liefern 404/501 oder werden nicht eingehängt.
   - **Compose-Profile:** Oxigraph läuft unter `profiles: ["rdf"]`. Standardinstallationen starten den Container gar nicht (0 MB RAM). Aktivierung via `COMPOSE_PROFILES=rdf` oder `katalon-cli`.

# Begründung

Für Katalon ist derzeit die optionale Aktivierung eines im Monorepo gepflegten Subsystems erforderlich. Compose-Profil und Feature-Flag decken diesen Umfang ab. Ein dynamischer Lifecycle für externe Erweiterungen würde zusätzliche Verträge für Persistenz, Hintergrundaufgaben und Berechtigungen benötigen; diese werden erst bei einem konkreten Erweiterungsbedarf bewertet.

# Citations

[1] GitHub Issue #364 (feat(rdf): Materialisierte RDF-Projektion in Oxigraph)
[2] GitHub Issue #358 (feat(rdf): Autorisierter, read-only SPARQL-Endpoint)
[3] GitHub Issue #359 (Discovery: RDF-Vertragstests und SHACL-Validierung)
[4] `almanac/decisions/platform/technology-stack.md`
[5] `almanac/decisions/operations/docker-customization-strategy.md`
[6] `almanac/decisions/platform/subsystem-extensions-vs-plugin-architecture.md`
