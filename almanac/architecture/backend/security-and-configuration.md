---
title: "Security And Configuration"
summary: "Katalon's backend combines environment-driven settings, production secret checks, JWT login, hashed API keys, role capabilities, encrypted application secrets, and request rate limits."
topics: [architecture, security, configuration, api]
sources:
  - id: public-metadata
    type: file
    path: backend/src/katalon/services/public_metadata_service.py
  - id: export-service
    type: file
    path: backend/src/katalon/services/export_service.py
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
  - id: management-cli
    type: file
    path: backend/src/katalon/management/cli.py
  - id: user-create-cli
    type: file
    path: backend/src/katalon/management/create_user.py
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
  - id: crawlers
    type: file
    path: backend/src/katalon/api/v1/crawlers.py
  - id: nginx-prod
    type: file
    path: docker/nginx.prod.conf
  - id: nginx-compose
    type: file
    path: docker/nginx.conf
---

Katalon's backend security boundary is built from configuration validation, first-run admin creation, JWT authentication, API-key authentication, role and capability checks, encrypted application secrets, and SlowAPI rate limiting. Settings are loaded through Pydantic `BaseSettings` from environment and `.env`, including database, Redis, Elasticsearch, Cantaloupe, JWT, media, CORS, admin, OAI, authority, DNB URN, and AI settings [@config]. FastAPI startup refuses insecure production defaults before mounting useful runtime behavior [@app].

The general `/v1` working API is authenticated: its routers are mounted with `get_current_user`, apart from login and token-refresh routes below `/v1/auth`. The unauthenticated exception is the deliberately narrow `/portal/v1` read model for published Portal content; it excludes Procedures and exposes explicit public response projections rather than internal API schemas [@app] [@portal-public].

The outer nginx configuration applies a CSP that permits the same-origin applications, configured HTTPS IIIF delivery endpoints, and embedded OpenStreetMap while disallowing plugins and third-party scripts. The Admin bundles IBM Plex locally instead of loading web fonts from a third party. Nginx also sends `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and `Permissions-Policy`; production TLS additionally sends HSTS.

Operators remain responsible for the legal information of their own deployment. [`docs/datenschutzerklaerung-vorlage.md`](../../../docs/datenschutzerklaerung-vorlage.md) is a configurable German privacy-notice template for a static Portal page; it lists only the optional integrations that must be retained when enabled.

## Configuration Inputs

`Settings` defines service URLs, `SECRET_KEY`, `KATALON_SECRETS_KEY`, fixed HS256 JWT signing, expiration windows, upload limits, media paths, default admin values, CORS origins, and integration credentials or toggles [@config]. The default `secret_key` is explicitly a development value, while `katalon_secrets_key` has a minimum length requirement in the settings model [@config].

Production startup checks are in `_check_production_secrets()`. When `debug` is false, startup raises if `SECRET_KEY` is a known default or shorter than 32 characters, or, when `KATALON_BASE_URL` is empty, if `INITIAL_ADMIN_PASSWORD` is empty or a known default password [@app]. That check happens at the start of the FastAPI lifespan [@app].

## First-Run Admin

Startup creates an admin user only when no `admin` or `superuser` exists [@app]. If `KATALON_BASE_URL` is set, the email is derived as `admin@<hostname>`, a random URL-safe password is generated, and the new account gets role `superuser` [@app]. The credentials are written to `settings.first_run_credentials_path` with file mode `0600` and are also logged as a first-run block [@app].

When `KATALON_BASE_URL` is empty, startup falls back to `DEFAULT_ADMIN_EMAIL` and `INITIAL_ADMIN_PASSWORD`, creates an `admin` role, and logs a warning about the fallback [@app]. This makes first-run behavior stricter for deployment-style setups than for local default setups.

## Creating Users from the CLI

Operators can create an account without using the Admin UI through `katalon-manage create-user --email <email> --password <password> --role <role>`. The command accepts `admin`, `superuser`, `editor`, `cataloger`, or `viewer`, validates the shared email and password contract, prevents duplicate email addresses, stores only the bcrypt password hash, and confirms the email and role without printing the password [@management-cli] [@user-create-cli] [@users].

## JWT And API Keys

Password login is handled by `/v1/auth/token`. It loads the user by email, verifies the bcrypt password hash, rejects inactive accounts, updates `User.last_login_at`, returns an access token, and sets the refresh token only as a host-only `HttpOnly`, `Secure`, `SameSite=Strict` cookie scoped to `/v1/` [@auth] [@models]. PyJWT signs tokens with the fixed HS256 algorithm and `settings.secret_key`; tokens include user id, role, email, token type, token version, and expiration [@auth]. `/v1/auth/refresh` reads that cookie and rotates it while issuing a new access token after the referenced active user is found with the same token version; `/v1/auth/logout` clears only the cookie in the calling browser and does not revoke tokens server-side. Access tokens live 60 minutes and refresh tokens 30 days, rolling on each refresh (`access_token_expire_minutes`, `refresh_token_expire_days`). There is no session table: the only revocation is incrementing `User.token_version`, which invalidates every token of that user on all devices. That happens on password reset, admin password change, own password change (`PUT /v1/users/me/password`, which returns a fresh token pair for the calling session), `POST /v1/auth/logout-others` (same mechanism on demand, exposed as "Sitzungen" card on the admin profile page), and `katalon-manage reset-admin` [@auth] [@users]. Login verifies against a dummy bcrypt hash for unknown emails so response time does not reveal which accounts exist [@auth].

`/v1/auth/password-reset` is unavailable before account lookup unless SMTP and `KATALON_BASE_URL` are configured. When available, it returns the same accepted response for known and unknown addresses, applies both the IP limit and a five-minute per-account SHA-256 cooldown, and stores only a SHA-256 hash of one 30-minute reset token. The delivery copy is Fernet-encrypted at rest; the request commits the row before queueing only its UUID, and the worker decrypts it after the broker boundary. `/v1/auth/password-reset/confirm` locks and consumes the token, changes the password, and increments `User.token_version`; existing access and refresh JWTs then fail validation [@auth] [@models] [@dependencies] [@secrets].

Authenticated dependencies try `X-API-Key` before Bearer tokens [@dependencies]. API keys must start with `ktn_`; the dependency looks up active candidates by stored prefix, bcrypt-checks the full supplied key, rejects expired keys, updates `last_used_at`, and returns the owning active user [@dependencies]. API-key management endpoints generate 192 bits of random hex, show the full key only in the creation response, and store only its bcrypt hash plus display prefix [@api-keys].

## Roles And Capabilities

User management accepts only `admin`, `superuser`, `editor`, `cataloger`, and `viewer` roles [@users]. The dependency layer maps roles to capabilities: viewers have none, catalogers and editors can manage content, admins and superusers can manage content, configuration, and users [@dependencies]. `require_role()` also lets `superuser` bypass role checks and lets higher editorial roles satisfy lower content roles [@dependencies].

The user endpoints enforce admin-only access for listing, creating, reading arbitrary users, updating users, deleting users, and admin API-key management [@users]. Self-service endpoints allow the current user to read their own user record, change password, change email, and manage their own API keys [@users] [@api-keys].

Configuration routers are still authenticated even when selected reads are not admin-only. Schema field reads and published static-page reads can be used by logged-in editorial users, while schema resets/imports and field mutations require `admin`; vocabulary mutations require `admin`; and static-page draft listing plus page create/update/delete use `require_admin()` [@app] [@schema-api] [@vocab-api] [@pages-api].

The fixed editorial roles `editor`, `cataloger`, and `viewer` have a persistent permission matrix for `read`, `create`, `update`, and `delete` across objects, entities, places, occurrences, and procedures. Admin and superuser retain unrestricted access. The backend enforces configured write rights and limits internal, non-published records to roles with read access; public portal visibility remains governed by publication status rather than the matrix [@dependencies] [@users] [@models].

Callers without `read` permission on a type (anonymous portal visitors and logged-in users lacking that permission) only ever see the public projection, and they only search it: the `q` filter of the record lists and the portal collection list matches public top-level fields and public subfields of public groups via `metadata_text_clause`, never internal fields or `file` values [@public-metadata]. Display titles on public surfaces (portal collection breadcrumbs and sub-collections, place hierarchy, export context for the record and its linked records) come from `public_title`, so an internal title field falls back to the idno instead of leaking [@public-metadata]. CSV/JSON dumps follow the same rule and return nothing for procedures and storage locations [@export-service].

## Stored Secrets And Rate Limits

Application secrets are stored in the `app_secrets` table through `secret_service`. The service derives a Fernet key from `KATALON_SECRETS_KEY` using SHA-256, encrypts values before writing, decrypts on read, and returns a 500 error when a stored value cannot be decrypted. Password-reset delivery tokens use the same encryption helper in `password_reset_tokens`, so plaintext reset tokens never enter Celery or Redis [@secrets] [@auth] [@email-tasks]. The same service defines `AI_API_KEY_SECRET` as the storage key for the AI API key [@secrets].

Rate limiting is anonymous/public-endpoint-focused and configurable via `.env`. `core/limiter.py` creates a SlowAPI `Limiter` keyed by remote address with `settings.rate_limit_default` (`200/minute` default) as the fallback limit for undecorated routes; `main.py` installs that limiter and its rate-limit exception handler on the FastAPI app [@limiter] [@app]. Explicitly decorated public endpoints read their own settings at request time via zero-arg lambdas so `.env` changes take effect without a code change: portal search (`RATE_LIMIT_PUBLIC_SEARCH`), OAI-PMH (`RATE_LIMIT_OAI`), the authenticated authority proxy (`RATE_LIMIT_AUTHORITY_PROXY`), and the anonymous single-record JSON-LD/Turtle export endpoints (`RATE_LIMIT_PUBLIC_EXPORT`) [@limiter]. Login and password-reset keep their brute-force-protection limits hardcoded rather than configurable, since they are a different threat model than crawler/scraper traffic.

Two deployment details decide whether those limits mean anything. First, the limiter key is `get_remote_address`, i.e. `request.client.host`. Behind nginx that is the proxy's address unless uvicorn rewrites it from `X-Forwarded-For`, which it only does for proxies listed in `FORWARDED_ALLOW_IPS`. `docker/Dockerfile.backend` therefore sets `FORWARDED_ALLOW_IPS="*"` and passes `--proxy-headers`; trusting every peer is sound because the `api` service publishes no host port and is reachable only through nginx on the compose network. Without that setting all traffic shares a single bucket keyed on the nginx container IP, so one crawler exhausts the limit and locks out ordinary visitors while never being throttled individually. Second, SlowAPI counters default to process-local memory, which undercounts across multiple workers or API containers; `RATE_LIMIT_STORAGE_URI` (Redis in the compose stack) moves them into shared storage. The limiter runs with `swallow_errors=True`, so a Redis outage degrades to no limiting instead of failing public requests — the same posture as `/health`, which deliberately omits Redis [@limiter].

A coarser prefilter sits in front of the application limit: `docker/nginx.conf` and `docker/nginx.prod.conf` define two `limit_req_zone`s keyed on `$binary_remote_addr` — `portal_read` (10 r/s, burst 20) on `/portal/v1/` and `portal_heavy` (2 r/s, burst 5) on `/oai` and `/sparql`, answering with 429 [@nginx-compose] [@nginx-prod]. Rejecting crawler bursts at the proxy keeps them off the API workers and their database connections entirely; SlowAPI remains the finer, per-endpoint stage behind it. Note the zones key on the direct peer, so an additional CDN or proxy in front would collapse them onto that hop's address.

Complementing this, the portal endpoints that every page view refetches and that change rarely — `/portal/v1/portal/config`, `/pages`, `/banners/active/portal`, `/theme` — send `Cache-Control: public, max-age=60`. `/portal/v1/schema/{target_type}` sends the same only for anonymous callers, together with `Vary: Authorization`; the staff projection additionally contains non-public field definitions and is returned as `private, no-store` [@portal-public]. The same viewer-dependent rule (`_cache_for_viewer`) covers the record reads behind detail pages and back navigation: `/objects/{id}`, `/entities/{id}`, `/places/{id}`, `/occurrences/{id}`, `/collections/{id}`, `/objects/{id}/media`, `/objects/{id}/iiif/manifest` and `/objects/summaries`. Endpoints without a staff projection (`/relations`, search-field terms, relation-type vocabularies) always send `public, max-age=60`. Error responses carry no cache header, and search results are not cached [@portal-public].

`api/v1/crawlers.py` (mounted at the root, alongside `/health` and `/oai`) serves `/robots.txt` (Disallow paths from `ROBOTS_DISALLOW_PATHS`, defaulting to `/v1/`) and `/llms.txt` (an LLM-agent-facing pointer to the JSON-LD/Turtle export endpoints and OAI-PMH instead of HTML scraping, toggled by `LLMS_TXT_ENABLED` and extendable via `LLMS_TXT_EXTRA_NOTES`) [@crawlers]. Both are advisory conventions only — they instruct well-behaved crawlers/agents but enforce nothing technically; actual abuse protection is the rate limiting above. Production nginx routes both paths to the API only on the public portal domain; the admin subdomain instead serves a static `Disallow: /` [@nginx-prod].

The same module serves `/sitemap.xml` (all publicly visible records of the five public types, `lastmod` from `updated_at`; above 50,000 URLs a sitemap index pointing to `?page=N`), and `robots.txt` adds a `Sitemap:` line when `KATALON_BASE_URL` is set. Because the portal is a client-rendered SPA, link-preview, search and AI crawlers would see only the empty HTML shell. nginx therefore matches the `User-Agent` against `$seo_bot` on the record URLs (`/objects|entities|places|occurrences|collections/<uuid>`) and rewrites those requests to `/portal/v1/seo/{plural}/{id}`, which `services/seo_service.py` renders from the anonymous public projection: `title`, `description`, `canonical`, `og:*`, `twitter:*` and a small schema.org JSON-LD block, with `og:image` from the object's primary public image. Non-public records answer 404. Absolute URLs use `KATALON_BASE_URL`, falling back to the request host. Humans and unknown bots keep getting the SPA; the bot list lives in the three nginx configs and must be extended there.

## Related Pages

Security checks run during [API Application Startup](api-application-startup). Deployment and environment details live in [Environment And Secrets](../../reference/operations/environment-and-secrets) and [Production Deployment](../../guides/operations/production-deployment).
