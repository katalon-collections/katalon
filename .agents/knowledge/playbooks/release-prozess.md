---
type: Playbook
title: Release-Prozess (Semver)
description: Mit jedem Commit die Patch-Version hochziehen; Minor/Major-Bumps brauchen Rücksprache mit Karl.
tags: [release, versionierung]
timestamp: 2026-07-09T00:00:00Z
---

# Trigger

Jeder Commit im Hauptrepo.

# Schritte

1. `backend/pyproject.toml` — `version = "x.y.z"`
2. `frontend/admin/package.json` — `"version": "x.y.z"`
3. `frontend/portal/package.json` — `"version": "x.y.z"`
4. `CHANGELOG.md` — neuer Eintrag unter `[Unreleased]` oder neuer `[x.y.z]`-Block
5. Nach dem Commit: `git tag vx.y.z && git push origin vx.y.z`

**Patch** (`0.1.x` → `0.1.x+1`): Standardfall, jeder Commit.
**Minor** (`0.1.x` → `0.2.0`): neue Features oder abgeschlossene Phase → kurz informieren, Karl entscheidet.
**Major** (`0.x.y` → `1.0.0`): erster öffentlicher Release → explizite Absprache.

# Citations

[1] Root `AGENTS.md`, Abschnitt "Versionierung"
