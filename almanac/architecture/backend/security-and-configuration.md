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
  - id: api-keys
    type: file
    path: backend/src/katalon/api/v1/api_keys.py
  - id: secrets
    type: file
    path: backend/src/katalon/services/secret_service.py
  - id: limiter
    type: file
    path: backend/src/katalon/core/limiter.py
---

Katalon's backend security boundary is built from configuration validation, first-run admin creation, JWT authentication, API-key authentication, role and capability checks, encrypted application secrets, and SlowAPI rate limiting. Settings are loaded through Pydantic `BaseSettings` from environment and `.env`, including database, Redis, Elasticsearch, Cantaloupe, JWT, media, CORS, admin, OAI, authority, DNB URN, Telegram, and AI settings [@config]. FastAPI startup refuses insecure production defaults before mounting useful runtime behavior [@app].

## Configuration Inputs

`Settings` defines service URLs, `SECRET_KEY`, `KATALON_SECRETS_KEY`, JWT algorithm and expiration windows, upload limits, media paths, default admin values, CORS origins, and integration credentials or toggles [@config]. The default `secret_key` is explicitly a development value, while `katalon_secrets_key` has a minimum length requirement in the settings model [@config].

Production startup checks are in `_check_production_secrets()`. When `debug` is false, startup raises if `SECRET_KEY` is a known default or shorter than 32 characters, or if `DEFAULT_ADMIN_PASSWORD` is a known default password [@app]. That check happens at the start of the FastAPI lifespan [@app].

## First-Run Admin

Startup creates an admin user only when no `admin` or `superuser` exists [@app]. If `KATALON_BASE_URL` is set, the email is derived as `admin@<hostname>`, a random URL-safe password is generated, and the new account gets role `superuser` [@app]. The credentials are written to `settings.first_run_credentials_path` with file mode `0600` and are also logged as a first-run block [@app].

When `KATALON_BASE_URL` is empty, startup falls back to `DEFAULT_ADMIN_EMAIL` and `DEFAULT_ADMIN_PASSWORD`, creates an `admin` role, and logs a warning about the fallback [@app]. This makes first-run behavior stricter for deployment-style setups than for local default setups.

## JWT And API Keys

Password login is handled by `/v1/auth/token`. It loads the user by email, verifies the bcrypt password hash, rejects inactive accounts, and returns an access/refresh token pair [@auth]. Tokens are JWTs signed with `settings.secret_key` and include user id, role, email, token type, and expiration [@auth]. `/v1/auth/refresh` accepts only refresh tokens and issues a new pair after the referenced active user is found [@auth].

Authenticated dependencies try `X-API-Key` before Bearer tokens [@dependencies]. API keys must start with `ktn_`; the dependency looks up active candidates by stored prefix, bcrypt-checks the full supplied key, rejects expired keys, updates `last_used_at`, and returns the owning active user [@dependencies]. API-key management endpoints generate 192 bits of random hex, show the full key only in the creation response, and store only its bcrypt hash plus display prefix [@api-keys].

## Roles And Capabilities

User management accepts only `admin`, `superuser`, `editor`, `cataloger`, and `viewer` roles [@users]. The dependency layer maps roles to capabilities: viewers have none, catalogers and editors can manage content, admins and superusers can manage content, configuration, and users [@dependencies]. `require_role()` also lets `superuser` bypass role checks and lets higher editorial roles satisfy lower content roles [@dependencies].

The user endpoints enforce admin-only access for listing, creating, reading arbitrary users, updating users, deleting users, and admin API-key management [@users]. Self-service endpoints allow the current user to read their own user record, change password, change email, and manage their own API keys [@users] [@api-keys].

Granular read, write, and delete permissions by record type, form, or action are not part of the current capability map; the dependency layer only exposes the coarse capabilities described above [@dependencies].

## Stored Secrets And Rate Limits

Application secrets are stored in the `app_secrets` table through `secret_service`. The service derives a Fernet key from `KATALON_SECRETS_KEY` using SHA-256, encrypts values before writing, decrypts on read, and returns a 500 error when a stored value cannot be decrypted [@secrets]. The same service defines `AI_API_KEY_SECRET` as the storage key for the AI API key [@secrets].

Rate limiting is global by default. `core/limiter.py` creates a SlowAPI `Limiter` keyed by remote address with `200/minute` as the default limit, and `main.py` installs that limiter and its rate-limit exception handler on the FastAPI app [@limiter] [@app].

## Related Pages

Security checks run during [API Application Startup](api-application-startup). Deployment and environment details live in [Environment And Secrets](../../reference/operations/environment-and-secrets) and [Production Deployment](../../guides/operations/production-deployment).
