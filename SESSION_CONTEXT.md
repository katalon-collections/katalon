## Changed

- Admin-Branding nutzt jetzt `site_title` aus der Portal-Konfiguration für Sidebar, Breadcrumbs und Browser-Tab im Admin.
- Admin-Auth hat jetzt Refresh-Token-Flow: Backend liefert `access_token` + `refresh_token`, Frontend erneuert Sessions automatisch.
- Backend-Auth-Tests erweitert; `backend/tests/integration/conftest.py` setzt Test-Secret und überspringt Cantaloupe-Healthcheck im Testkontext.
- `backend/pyproject.toml` und `backend/uv.lock` auf `click-didyoumean==0.3.1` stabilisiert.
- `CHANGELOG.md`, `backend/pyproject.toml`, `frontend/admin/package.json` und `frontend/portal/package.json` auf `0.3.5` gehoben.
- Release `v0.3.5` nach GitHub gepusht.

## Decided

- Bereits vorhandenes Remote-Tag `v0.3.4` nicht überschreiben; neuer Release wurde daher als `v0.3.5` geschnitten.
- Backend-Python-Kommandos sollen aus `backend/` laufen, weil Repo-Root eine andere `.venv` hat und sonst falsche Dependencies geladen werden.
- Inkonsistenter `uv.lock`-Eintrag fuer `click-didyoumean` wird bis auf Weiteres durch explizites Pinning auf `0.3.1` abgefangen.

## Pending

- `SESSION_CONTEXT.md` selbst ist lokal uncommitted und absichtlich nicht Teil des Releases.
- Backend-Testlauf braucht fuer Full Suite weiter `KATALON_SECRETS_KEY=test-katalon-secrets-key-32-chars`.
- Full Suite braucht Redis auf `localhost:6379`; dafuer Redis mit Dev-Overlay starten (`docker-compose.dev.yml` bindet Port 6379).
- Testlauf zeigt weiterhin bestehende Warnings zu Pydantic-`Config` und `Unclosed client session`.

## State

Projektstand auf `main`/`origin/main` bei Commit `f098ba8` und Tag `v0.3.5`. Release ist draussen und verifiziert: Backend-Testsuite lief gruen (`284 passed`) mit gesetztem Test-Secret und lokal gebundenem Redis; Admin- und Portal-Build sind ebenfalls gruen. Lokaler Arbeitsbaum ist bis auf diese `SESSION_CONTEXT.md` sauber.
