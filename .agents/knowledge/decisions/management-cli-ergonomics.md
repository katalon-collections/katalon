---
type: Decision
title: Management-CLI-Ergonomie: uv-Workspace-Root und source-relative .env
description: Repo-Root ist ein uv-Workspace (members=["backend"]), katalon-manage ist aus jedem Verzeichnis nutzbar, Settings löst .env source-relativ auf, und fehlender KATALON_SECRETS_KEY meldet sich lesbar ohne Stacktrace.
tags: [cli, uv, config, operations]
timestamp: 2026-08-20T00:00:00Z
---

# Kontext

`katalon-manage` musste bisher aus `backend/` mit gesetztem
`KATALON_SECRETS_KEY` gestartet werden; ohne die Env-Var brach der Aufruf mit
einem Pydantic-Stacktrace ab, und die `.env` (Repo-Root) wurde nur geladen,
wenn das Arbeitsverzeichnis passte. Für Dev/Ops wurde eine Last einfacher
Befehle gewünscht ("aus dem Main-Ordner nutzbar").

# Entscheidung

- Das Repo-Root trägt ein `pyproject.toml` mit `[tool.uv.workspace]
  members = ["backend"]`. `uv run katalon-manage` (und `uv run pytest`) ist
  damit direkt aus dem Repo-Root nutzbar; effektiver Lock ist das Root-
  `uv.lock`, `backend/uv.lock` ist verwaist.
- `Settings` löst `.env` source-relativ auf (`backend/.env`, dann Root-`.env`
  mit höherer Priorität), unabhängig vom Arbeitsverzeichnis.
- Fehlender/zu kurzer `KATALON_SECRETS_KEY` wirft `KatalonSecretsKeyError`
  (`katalon.errors`, settings-frei). Der `katalon-manage`-Launcher
  (`katalon.management.runner`) fängt ihn und gibt eine einzelne lesbare
  Zeile auf stderr aus (Exit 1) statt eines Stacktraces.

# Begründung

- **Workspace statt Root-Script-Wrapper**: `uv` löst Package- und Interpreter-
  Auflösung selbst; kein Heuhaufen von Assistent-Wrappern (Makefile/`source`
  Zauber) nötig.
- **Source-relative .env**: Der Config-Punkt ist jetzt cwd-unabhängig; CI,
  Containern und lokal gilt dieselbe Regel.
- **Settings-freie Exception**: erst durch den Zwischenbau von `errors.py`
  wird der Stacktrace-Pfad ausgeschaltet, ohne Pydantic in der Importkette zu
  bedienen.

# Citations

[1] `backend/src/katalon/config.py` (`_resolve_env_files`, `KatalonSecretsKeyError`)
[2] `backend/src/katalon/errors.py`
[3] `backend/src/katalon/management/runner.py`
[4] Root `pyproject.toml` (uv workspace)