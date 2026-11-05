---
type: Playbook
title: Release-Prozess (Semver, Tag erst nach grüner CI)
description: Release-Dateien und Prüfungen abstimmen; Veröffentlichung bleibt beim Maintainer und folgt dem kuratierten Export.
tags: [release, versionierung]
timestamp: 2026-10-24T00:00:00Z
---

# Trigger

Ein Feature-Set oder Bugfix-Paket ist fertig — nicht jeder Commit.

# Zuständigkeit

Beiträge kommen über den Workflow in `CONTRIBUTING.md`. Versionssprünge, Tags
und Veröffentlichung erfordern einen ausdrücklichen Release-Auftrag. Private
Remote-Namen und Freigaben stehen ausschließlich in der lokalen Ergänzung
`.agents/maintainer/AGENTS.md`, sofern sie vorhanden ist.

# Release-Prüfliste

1. Version synchron: `backend/pyproject.toml`, `frontend/admin/package.json`,
   `frontend/portal/package.json`, `CHANGELOG.md` (`[x.y.z]`-Block), `openapi.json`
   (`uv run python scripts/gen_openapi.py`).
2. `release-meta.toml`: `[images]`/`[requires]` (Fremdservices, siehe
   [Release bestimmt Fremdservice-Images](../decisions/release-bestimmt-fremdservice-images.md)),
   `[releases."x.y.z"]` (`reindex_required`, env_vars), `minimum_installer_version`.
3. Minor-Release: `CHANGELOG.public.md` um die neuen Features und, ab 1.49.0, die Fehlerbehebungen ergänzen (Endnutzertext; keine internen Refactorings, CI/Tests, reine Doku).
4. Release-Prüfungen und CI abwarten: Backend, Frontend, Security einschließlich
   Abhängigkeitsprüfungen. Fehler vor dem Tag klären.
5. Maintainer prüft Zielrepository und Exportumfang vor der Veröffentlichung.
   Private Historie darf niemals direkt zum öffentlichen Remote gepusht werden.
6. Öffentlichen Export, Release-Metadaten und Container-Images jeweils separat
   verifizieren; ein grüner privater CI-Lauf beweist keine öffentliche Distribution.

**Patch:** Fixes. **Minor:** neue Features → mit dem Maintainer abstimmen.
**Major:** Breaking Changes → explizite Absprache.

# Citations

[1] Root `AGENTS.md`, Abschnitte „Versionierung, Review und Veröffentlichung“, „Production-Installation“
[3] `CONTRIBUTING.md` — Beitragsworkflow und Prüfung
[2] [Public-Repo hat disjunkte Historie](../gotchas/public-repo-disjoint-history.md)
