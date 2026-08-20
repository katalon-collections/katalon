# Backend Coding Rules (Python / FastAPI)

Gilt für `backend/`. Extrahiert aus `backend/pyproject.toml`, root `AGENTS.md` und `docs/CODE_QUALITY_ASSESSMENT.md`.

## Tooling & Ausführung

- Immer `uv` für Package-Management, `uv venv` für virtuelle Umgebungen. Nie `pip` direkt.
- Backend-Python-Kommandos nach Möglichkeit aus `backend/` ausführen. Das Repo-Root ist seit dem uv-Workspace (`pyproject.toml` mit `[tool.uv.workspace] members = ["backend"]`) für `uv run` direkt nutzbar (z. B. `uv run katalon-manage`); `Settings` löst `.env` source-relativ auf (backend + Root).
- `click-didyoumean==0.3.1` gepinnt halten — `uv` stolpert sonst über einen inkonsistenten Lock-Eintrag. Effektiver Lock ist seit dem uv-Workspace das Root-`uv.lock` (nicht `backend/uv.lock`). Nicht ändern bis Upstream sauber ist.
- Python 3.12+, `hatchling`-Build.

## Lint & Types

- `ruff` (`line-length = 100`, `target-version = "py312"`), Regeln: `E`, `W`, `F`, `I`, `UP`; `E501` ignoriert (Line-Length wird nicht hart erzwungen, andere Regeln schon).
- Vor Commit: `uvx ruff check --fix`.
- `mypy strict = true`, `ignore_missing_imports = true`. Neuer Code muss typisiert sein.
- `pytest`, `asyncio_mode = "auto"`, Testpfad `backend/tests/`.

## Muster, die im Code bereits gelten (einhalten)

- Klare Trennung `api/` (Endpoints) / `services/` (Business-Logik) / `integrations/` (ES, Cantaloupe, Authority-Adapter) / `workers/` (Celery Tasks). Neuer Code folgt dieser Schichtung, keine Business-Logik in Endpoint-Handlern.
- Parametrisiertes SQL durchgängig (SQLAlchemy) — nie String-Interpolation in Queries.
- Passwörter **und** API-Keys über `bcrypt`.
- Rollen/Enum-Felder (z. B. `role`) nie als freier String akzeptieren — `Literal`/`Enum` verwenden und validieren (siehe `docs/CODE_QUALITY_ASSESSMENT.md`, Finding M2 — an dieser Stelle noch offen, aber die Regel gilt für allen neuen Code).

## Explizit vermeiden

- `except Exception: pass` ohne Logging — verschluckt Fehler stillschweigend (siehe Finding M4). Mindestens `logger.warning(..., exc_info=True)`.
- Neue Endpoints ohne `CurrentUser`/`require_role`-Dependency, wenn sie schreibend oder privilegiert sind (siehe Finding C1 — unauthentifizierte Self-Registration mit frei wählbarer Rolle war ein kritischer Fund).
- Synchrone Elasticsearch-Indizierung im Request-Pfad ohne Retry/Reconciliation-Pfad (siehe Finding M3, mittlerweile durch Issue #214 gelöst — Muster nicht wiederholen).

## Citations

[1] `backend/pyproject.toml`
[2] Root `AGENTS.md`, Abschnitte "Python/uv Hinweise", "Kritische Build-Konfigurationen"
[3] `docs/CODE_QUALITY_ASSESSMENT.md`
