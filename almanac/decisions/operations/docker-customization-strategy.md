---
title: "Docker Customization Strategy"
summary: "Routine deployment customization uses compose overrides and mounts instead of rebuilding core images."
topics: [decisions, operations, docker, deployment, customization]
sources:
  - id: decision-note
    type: file
    path: .agents/knowledge/decisions/docker-customization-strategy.md
  - id: override-example
    type: file
    path: docker-compose.override.yml.example
  - id: customization-doc
    type: file
    path: docs/06_anpassungen.md
---

Katalon's deployment customization strategy keeps routine local changes outside the core Docker images. The recorded decision chooses `docker-compose.override.yml`, mounted customization directories, and `PYTHONPATH` extension for branding and authority adapters, so installations can pull updated images without rebuilding for common changes [@decision-note]. The repository includes an override example for service-specific ports, environment variables, and volume paths, and the customization guide describes extension points for authority adapters and portal UI changes [@override-example] [@customization-doc].

## Context

Katalon is a Docker-first application, so image updates should stay close to `docker compose pull` followed by `docker compose up -d` [@decision-note]. Instance-specific branding and adapters still need to survive those updates, and rebuilding a downstream image for every small local change would make the simple deployment path harder than the project wants for MVP installations [@decision-note].

The customization guide shows that not every change has the same weight. Adding a built-in authority adapter requires a Python module and registry entry, while database-registered external adapters can be loaded by full Python path when the module is importable on `PYTHONPATH` [@customization-doc]. Portal layout and route changes are ordinary React edits under `frontend/portal/src`, while theme colors can also come from admin settings persisted in `portal_config` [@customization-doc].

## Decision

Use compose overrides and mounts for routine deployment customization. The decision note sets MVP customization scope to branding and authority adapters, keeps templates and custom field types post-MVP, and names `docker-compose.override.yml` as the pattern that keeps the main compose file updateable [@decision-note]. It also chooses mounted `custom/` static and template directories for assets, mounted plugin directories plus `PYTHONPATH` for MVP plugins, and downstream Docker images only for production teams that already own a build pipeline [@decision-note].

The checked-in override example follows that contract. It shows an override file that changes the nginx HTTPS port, adds an API environment variable, and replaces the database volume path without editing the base compose file [@override-example].

## Consequences

Routine local deployment changes should start with an override file or a mount. This keeps image updates boring: pull the published images, restart the stack, and run migrations, while manually merging `.env` or compose changes remains the operator's responsibility [@decision-note].

Core-image rebuilds are still allowed when they are the right operational tool. The decision note reserves downstream images for production plugin packaging with installed Python dependencies, where rebuilds are acceptable because the institution owns a build pipeline [@decision-note]. The lazy default is therefore not "never rebuild"; it is "do not rebuild core images for changes a compose override or mounted adapter can handle."

This decision is operational, not a promise that every customization surface is runtime-loaded. The current guide still describes source edits for some portal UI changes and a registry edit for adding a core authority adapter [@customization-doc]. Use the override strategy first for deployment-local configuration, and escalate to code or downstream image changes only when the extension cannot be expressed as a mounted file, importable adapter, environment variable, or volume.
