---
type: Gotcha
title: Backend-Testsuite braucht KATALON_SECRETS_KEY
description: pytest ohne gesetztes KATALON_SECRETS_KEY bricht in der Collection mit 27 pydantic ValidationErrors ab — die Suite läuft nie an. Env-Var vor dem Lauf setzen.
tags: [backend, testing, pytest, uv, config]
timestamp: 2026-07-10T00:00:00Z
---

# Symptom

`uv run pytest` aus `backend/` bricht in der Collection ab:

```
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
katalon_secrets_key
  Field required [type=missing, ...]
!!!!! Interrupted: 27 errors during collection !!!!!
```

Kein einziger Test läuft — reiner Collection-Fehler in ~27 Dateien, die `config`/`models`
importieren.

# Ursache

`settings.katalon_secrets_key` ist in `backend/src/katalon/config.py` ein Pflichtfeld
(`Field(min_length=32)`, kein Default). Beim Import von `config` (transitiv über fast
jedes Modul) wird `Settings()` instanziiert und schlägt ohne die Env-Var fehl.

Es gibt kein `.env`, kein `tests/conftest.py` auf Root-Ebene und kein Makefile-Test-Target,
das die Var setzt — nur `tests/integration/conftest.py` setzt sie (für die Integrationsläufe).
Ein blanker `pytest`-Aufruf erbt sie also nicht.

# Fix / Vorbeugung

Env-Var vor dem Lauf setzen (Wert egal, nur `min_length=32`; identisch zu
`tests/integration/conftest.py::TEST_SECRETS_KEY`):

```bash
cd backend
KATALON_SECRETS_KEY="test-katalon-secrets-key-32-chars" uv run pytest -q
```

Seit dem uv-Workspace und der source-relativen `.env`-Auflösung kann dieselbe
Variable auch aus dem Repo-Root kommen und den Lauf schon ohne manuelles Export
versorgen: `Settings` liest `backend/.env` und Root-`.env`, und `uv run
katalon-manage` / `uv run pytest` sind aus dem Root nutzbar. Die explizite
Env-Var-Form oben bleibt die dokumentierte, umgebungsunabhängige Variante.

Nicht im `api`-Container laufen lassen — das ist ein Prod-Image ohne `pytest`.

# Citations

[1] `backend/src/katalon/config.py` (`katalon_secrets_key: str = Field(min_length=32)`)
[2] `backend/tests/integration/conftest.py` (`TEST_SECRETS_KEY`)
