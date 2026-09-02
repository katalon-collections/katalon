---
title: "Security And Configuration"
summary: "Katalon's backend combines environment-driven settings, production secret checks, JWT login, hashed API keys, role capabilities, encrypted application secrets, and request rate limits."
topics: [architecture, security, configuration, api]
sources:
  - id: config
    type: file
    path: backend/src/katalon/config.py
  - id: app
    type: file
    path: backend/src/katalon/main.py
  - id: auth
    type: file
    path: backend/src/katalon/api/v1/auth.py
  - id: dependencies
    type: file
    path: backend/src/katalon/core/dependencies.py
  - id: users
    type: file
    path: backend/src/katalon/api/v1/users.py
  - id: screen-users
    type: file
    path: frontend/admin/src/components/screens/ScreenUsers.tsx
  - id: schema-api
    type: file
    path: backend/src/katalon/api/v1/schema_admin.py
  - id: vocab-api
    type: file
    path: backend/src/katalon/api/v1/vocabularies.py
  - id: pages-api
    type: file
    path: backend/src/katalon/api/v1/pages.py
  - id: models
    type: file
    path: backend/src/katalon/core/models.py
  - id: api-keys
    type: file
    path: backend/src/katalon/api/v1/api_keys.py
  - id: portal-public
    type: file
    path: backend/src/katalon/api/v1/portal_public.py
  - id: secrets
    type: file
    path: backend/src/katalon/services/secret_service.py
  - id: email-tasks
    type: file
    path: backend/src/katalon/workers/email_tasks.py
  - id: limiter
    type: file
    path: backend/src/katalon/core/limiter.py
---

Katalon's backend security boundary is built from configuration validation, first-run admin creation, JWT authentication, API-key authentication, role and capability checks, encrypted application secrets, and SlowAPI rate limiting. Settings are loaded through Pydantic `BaseSettings` from environment and `.env`, including database, Redis, Elasticsearch, Cantaloupe, JWT, media, CORS, admin, OAI, authority, DNB URN, Telegram, and AI settings [@config]. FastAPI startup refuses insecure production defaults before mounting useful runtime behavior [@app].

The general `/v1` working API is authenticated: its routers are mounted with `get_current_user`, apart from login and token-refresh routes below `/v1/auth`. The unauthenticated exception is the deliberately narrow `/portal/v1` read model for published Portal content; it excludes Procedures and exposes explicit public response projections rather than internal API schemas [@app] [@portal-public].

The outer nginx configuration applies a CSP that permits the same-origin applications, configured HTTPS IIIF delivery endpoints, and embedded OpenStreetMap while disallowing plugins and third-party scripts. The Admin bundles IBM Plex locally instead of loading web fonts from a third party. Nginx also sends `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and `Permissions-Policy`; production TLS additionally sends HSTS.

Operators remain responsible for the legal information of their own deployment. [`docs/datenschutzerklaerung-vorlage.md`](../../../docs/datenschutzerklaerung-vorlage.md) is a configurable German privacy-notice template for a static Portal page; it lists only the optional integrations that must be retained when enabled.

## Configuration Inputs

`Settings` defines service URLs, `SECRET_KEY`, `KATALON_SECRETS_KEY`, JWT algorithm and expiration windows, upload limits, media paths, default admin values, CORS origins, and integration credentials or toggles [@config]. The default `secret_key` is explicitly a development value, while `katalon_secrets_key` has a minimum length requirement in the settings model [@config].

Production startup checks are in `_check_production_secrets()`. When `debug` is false, startup raises if `SECRET_KEY` is a known default or shorter than 32 characters, or if `DEFAULT_ADMIN_PASSWORD` is a known default password [@app]. That check happens at the start of the FastAPI lifespan [@app].

## First-Run Admin

Startup creates an admin user only when no `admin` or `superuser` exists [@app]. If `KATALON_BASE_URL` is set, the email is derived as `admin@<hostname>`, a random URL-safe password is generated, and the new account gets role `superuser` [@app]. The credentials are written to `settings.first_run_credentials_path` with file mode `0600` and are also logged as a first-run block [@app].

When `KATALON_BASE_URL` is empty, startup falls back to `DEFAULT_ADMIN_EMAIL` and `DEFAULT_ADMIN_PASSWORD`, creates an `admin` role, and logs a warning about the fallback [@app]. This makes first-run behavior stricter for deployment-style setups than for local default setups.

## JWT And API Keys

Password login is handled by `/v1/auth/token`. It loads the user by email, verifies the bcrypt password hash, rejects inactive accounts, updates `User.last_login_at`, returns an access token, and sets the refresh token only as a host-only `HttpOnly`, `Secure`, `SameSite=Strict` cookie scoped to `/v1/auth` [@auth] [@models]. Tokens are JWTs signed with `settings.secret_key` and include user id, role, email, token type, token version, and expiration [@auth]. `/v1/auth/refresh` reads that cookie and rotates it while issuing a new access token after the referenced active user is found with the same token version; `/v1/auth/logout` clears it [@auth]. The admin user list displays `last_login_at` for admin and superuser operators; accounts that have not logged in since the column existed render an empty value [@users] [@screen-users].

`/v1/auth/password-reset` is unavailable before account lookup unless SMTP and `KATALON_BASE_URL` are configured. When available, it returns the same accepted response for known and unknown addresses, applies both the IP limit and a five-minute per-account SHA-256 cooldown, and stores only a SHA-256 hash of one 30-minute reset token. The delivery copy is Fernet-encrypted at rest; the request commits the row before queueing only its UUID, and the worker decrypts it after the broker boundary. `/v1/auth/password-reset/confirm` locks and consumes the token, changes the password, and increments `User.token_version`; existing access and refresh JWTs then fail validation [@auth] [@models] [@dependencies] [@secrets].

Authenticated dependencies try `X-API-Key` before Bearer tokens [@dependencies]. API keys must start with `ktn_`; the dependency looks up active candidates by stored prefix, bcrypt-checks the full supplied key, rejects expired keys, updates `last_used_at`, and returns the owning active user [@dependencies]. API-key management endpoints generate 192 bits of random hex, show the full key only in the creation response, and store only its bcrypt hash plus display prefix [@api-keys].

## Roles And Capabilities

User management accepts only `admin`, `superuser`, `editor`, `cataloger`, and `viewer` roles [@users]. The dependency layer maps roles to capabilities: viewers have none, catalogers and editors can manage content, admins and superusers can manage content, configuration, and users [@dependencies]. `require_role()` also lets `superuser` bypass role checks and lets higher editorial roles satisfy lower content roles [@dependencies].

The user endpoints enforce admin-only access for listing, creating, reading arbitrary users, updating users, deleting users, and admin API-key management [@users]. Self-service endpoints allow the current user to read their own user record, change password, change email, and manage their own API keys [@users] [@api-keys].

Configuration routers are still authenticated even when selected reads are not admin-only. Schema field reads and published static-page reads can be used by logged-in editorial users, while schema resets/imports and field mutations require `admin`; vocabulary mutations require `admin`; and static-page draft listing plus page create/update/delete use `require_admin()` [@app] [@schema-api] [@vocab-api] [@pages-api].

The fixed editorial roles `editor`, `cataloger`, and `viewer` have a persistent permission matrix for `read`, `create`, `update`, and `delete` across objects, entities, places, occurrences, and procedures. Admin and superuser retain unrestricted access. The backend enforces configured write rights and limits internal, non-published records to roles with read access; public portal visibility remains governed by publication status rather than the matrix [@dependencies] [@users] [@models].

## Stored Secrets And Rate Limits

Application secrets are stored in the `app_secrets` table through `secret_service`. The service derives a Fernet key from `KATALON_SECRETS_KEY` using SHA-256, encrypts values before writing, decrypts on read, and returns a 500 error when a stored value cannot be decrypted. Password-reset delivery tokens use the same encryption helper in `password_reset_tokens`, so plaintext reset tokens never enter Celery or Redis [@secrets] [@auth] [@email-tasks]. The same service defines `AI_API_KEY_SECRET` as the storage key for the AI API key [@secrets].

Rate limiting is global by default. `core/limiter.py` creates a SlowAPI `Limiter` keyed by remote address with `200/minute` as the default limit, and `main.py` installs that limiter and its rate-limit exception handler on the FastAPI app [@limiter] [@app].

## Related Pages

Security checks run during [API Application Startup](api-application-startup). Deployment and environment details live in [Environment And Secrets](../../reference/operations/environment-and-secrets) and [Production Deployment](../../guides/operations/production-deployment).
