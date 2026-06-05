# Katalon – Code Quality Assessment

Date: 2026-06-05 (updated after remediation commit `d5f326f`)
Scope: `backend/src` (77 files, ~9.7k LOC Python) + `frontend/{admin,portal}` (60 TS/TSX files)
Tools: `ruff 0.x`, manual review, pattern grep, codegraph index.

**Remediation status:** C1, H1, M1 fixed in `d5f326f`. M2–M4 and all Low items still open.

---

## Summary

Architecture is sound and modern (FastAPI + async SQLAlchemy + Pydantic v2, clean
service/api/integration separation, parameterized SQL throughout, bcrypt for both
passwords and API keys). Frontend is unusually clean: zero `any`, zero `console.log`,
and the single `dangerouslySetInnerHTML` is wrapped in DOMPurify.

The original review found **one critical, unauthenticated privilege-escalation
vector** and **one guaranteed runtime crash bug**, plus lint hygiene that contradicts
the documented pre-commit policy. The two top items and one Medium have since been
fixed; the rest remain.

| Severity | Status | Headline |
|----------|--------|----------|
| Critical | ✅ fixed `d5f326f` | Unauthenticated `/auth/register` accepts arbitrary `role` |
| High | ✅ fixed `d5f326f` | `IntegrityError` undefined → `NameError` at runtime |
| Medium | ✅ fixed `d5f326f` | M1 — mock URN router mounted in production |
| Medium | ⬜ open | M2 role not validated, M3 ES/DB drift, M4 broad `except: pass` |
| Low | ⬜ open | 214 ruff violations, JWT claims, CORS config drift |

---

## Critical

### C1 — Unauthenticated admin/superuser self-registration — ✅ FIXED (`d5f326f`)
Resolved by deleting the route. Real user creation already lives on the admin-guarded,
role-validated `/v1/users` endpoint. Original finding below.

`backend/src/katalon/api/v1/auth.py:39`

```python
@router.post("/register", response_model=UserRead, status_code=201)
async def register(data: UserCreate, db: DBDep) -> User:
```

No `CurrentUser` / `require_role` dependency. `UserCreate` (`core/schemas.py:177`)
exposes `role: str = "viewer"` as a free-form client-supplied string. Anyone who can
reach the API can POST:

```json
{"email":"x@x.com","password":"abc12345","role":"superuser"}
```

and obtain a superuser account — full takeover. `require_role` (`dependencies.py:129`)
treats `superuser` as bypassing all checks, so this is total.

The frontend does **not** call this endpoint (verified — admin uses `/auth/token`
only; user creation goes through the guarded `users` router). The endpoint appears to
be dead/legacy but is mounted (`main.py:338`).

**Fix:** either delete the route, or guard it with `require_admin()` **and** validate
`role` against an enum (`Literal["viewer","editor","cataloger","admin"]`, never allow
`superuser` from request body). Apply the same enum to `users` create path.

---

## High

### H1 — `IntegrityError` undefined name (runtime crash) — ✅ FIXED (`d5f326f`)
Resolved: added `from sqlalchemy.exc import IntegrityError`. Original finding below.

`backend/src/katalon/api/v1/importer.py:326` — ruff `F821`

```python
try:
    await db.flush()
except IntegrityError:   # <-- never imported
    await db.rollback()
```

`IntegrityError` is not imported in the module. When a flush actually violates a
constraint, the `except` clause itself raises `NameError`, masking the real error and
skipping the rollback/restore logic. This is the recovery path for the
restore-deleted-fields branch, so it only fires under conflict — i.e. exactly when it
matters.

**Fix:** `from sqlalchemy.exc import IntegrityError`.

---

## Medium

### M1 — Mock URN router mounted unconditionally in production — ✅ FIXED (`d5f326f`)
Resolved: inclusion now gated behind `if settings.debug:` in `main.py`. Original finding below.

`backend/src/katalon/main.py:362` → `api/v1/dnb_urn_mock.py`

The in-memory DNB-URN **mock** registrar is included on every startup regardless of
`settings.dnb_urn_enabled` or `debug`. It exposes `/v1/dnb-urn-mock/*` writable
endpoints backed by a module-global dict in production.

**Fix:** gate inclusion behind `if settings.debug:` (or `dnb_urn_enabled` + a test
flag) in `main.py`.

### M2 — `role` accepted as unvalidated free string
`core/schemas.py:180`. Beyond C1, even guarded user-creation paths accept any string
as a role. A typo (`"editorr"`) silently creates a user who matches no `require_role`
set. Use a `Literal`/`Enum` and validate.

### M3 — Elasticsearch indexed synchronously in request path; DB commits even on index failure
`api/v1/objects.py:121` (and the parallel entities/places/occurrences handlers).

```python
try:
    await search_service.index_record("object", obj, db)
except Exception:
    logger.warning("ES index/remove failed", exc_info=True)
return obj   # db.get_db commits anyway -> record exists, ES does not
```

Failure is logged (good — better than the older silent `pass`), but the request still
succeeds and the row is committed, producing permanent ES/DB drift with no
reconciliation. Celery `index_tasks` exist but are unused. This is the known Issue #214
surface — worth prioritizing: move indexing to a Celery task with retry, or add a
reconciliation sweep.

### M4 — Broad `except Exception: pass` without logging
`services/publish_service.py:97,103`, `services/authority_service.py:60`,
`workers/import_tasks.py:360`. Several swallow all exceptions with no log line, hiding
failures (publish side-effects, cache invalidation). The `main.py:310` ES-bootstrap one
is acceptable (commented, startup-optional); the service-layer ones should at least
`logger.warning(..., exc_info=True)`.

---

## Low

### L1 — 214 ruff violations; pre-commit policy not enforced
`uvx ruff check src` → **214 errors**:

| Rule | Count | Note |
|------|-------|------|
| E501 line-too-long | 165 | line-length=100 configured |
| E402 import-not-at-top | 40 | caused by `logger = getLogger(...)` placed mid-import in objects/entities/places/occurrences |
| UP035 deprecated-import | 4 | `typing.X` → builtins |
| F841 unused-variable | 2 | `iconclass_adapter.py:25`, `xml_format.py:102` |
| I001 unsorted-imports | 2 | autofixable |
| F821 undefined-name | 1 | = H1 above |

`AGENTS.md`/CLAUDE.md claim a linter runs pre-commit, but these are committed. Either
the hook isn't installed or it's bypassed. `mypy --strict` is configured but the
backlog suggests it isn't gating either.

**Fix:** `uvx ruff check --fix src` clears 6 immediately; the E402 batch is a
mechanical "move `logger=` below imports" in 4 files; then wire ruff+mypy into CI so it
stays green.

### L2 — JWT has no `iss`/`aud`, no token revocation
`auth.py:30`. `exp` is set and jose validates it — fine. But there's no issuer/audience
binding and no revocation list; a leaked token is valid for the full 8h window. Low risk
given scope, note for hardening (Phase 12).

### L3 — CORS origin list drift + permissive credentials
`config.py:40`. `allow_credentials=True` with `allow_methods=["*"]`,
`allow_headers=["*"]`. Origins are an explicit allowlist (good) but include phantom
`http://localhost:4000/4001` that per project memory never existed in docker-compose.
Prune to real origins; keep wildcard methods/headers only because the allowlist is
explicit (acceptable, but document it).

---

## What's good (keep doing)

- **No SQL injection surface** — all DB access via SQLAlchemy core/ORM; the one raw
  `text()` (`idno_service.py:45`) uses bound params.
- **No `eval`/`exec`/`pickle`/`subprocess`/`shell=True`** anywhere in backend.
- **Password & API-key handling**: bcrypt with per-value salt; API keys stored hashed,
  looked up by 12-char prefix then bcrypt-compared; password strength validator.
- **Production safety gate**: `_check_production_secrets()` refuses startup with default
  `SECRET_KEY`/admin password when `debug=False`. First-run generates a random
  superuser password and writes it `0o600`.
- **Frontend hygiene**: 0 `: any`, 0 `console.log`, DOMPurify on the only raw-HTML sink.
- **Idempotent bootstrap**: all `_ensure_*` startup helpers are guard-checked.

---

## Suggested order of work

1. ~~**C1** — guard/delete `/auth/register`~~ ✅ done `d5f326f` (route deleted).
2. ~~**H1** — import `IntegrityError`~~ ✅ done `d5f326f`.
3. ~~**M1** — gate `dnb_urn_mock` behind `debug`~~ ✅ done `d5f326f`.
4. **M2** — replace free-string `role` with a `Literal`/`Enum` on the `/v1/users` path.
5. **L1** — `ruff --fix`, fix E402 logger placement, re-enable the pre-commit hook + CI.
6. **M3/M4** — move ES indexing to Celery + add logging to silent excepts (folds into
   Issues #213/#214 already on the roadmap).
7. **L2/L3** — JWT claims + CORS pruning during Phase 12 hardening.
