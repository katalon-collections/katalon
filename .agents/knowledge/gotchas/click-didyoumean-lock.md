---
type: Gotcha
title: click-didyoumean Lock-Inkonsistenz bricht uv
description: Der Lock-Eintrag für click-didyoumean zeigt auf 0.3.2, referenziert aber click_didyoumean-0.3.1-Dateien — uv install schlägt fehl, bis die Version auf 0.3.1 gepinnt ist.
tags: [backend, uv, dependencies]
timestamp: 2026-07-09T00:00:00Z
---

# Symptom

`uv sync`/`uv pip install` in `backend/` schlägt fehl oder installiert falsche Dateien
für `click-didyoumean`.

# Ursache

Der effektive Lock ist seit dem uv-Workspace das Root-`uv.lock` (Repo-Root
`pyproject.toml` mit `members = ["backend"]`); `backend/uv.lock` ist dadurch
verwaist. In ungültigen Zuständen steht dort ein inkonsistenter Eintrag für
`click-didyoumean`: `version = "0.3.2"` zeigt auf
`click_didyoumean-0.3.1`-Dateien.

# Fix / Vorbeugung

`click-didyoumean==0.3.1` in `backend/pyproject.toml` gepinnt lassen, bis Upstream den
Lock-Eintrag sauber macht. Nicht versuchen, auf 0.3.2 zu aktualisieren, ohne den
Lock-Zustand vorher zu prüfen.

# Citations

[1] Root `AGENTS.md`, Abschnitt "Python/uv Hinweise"
