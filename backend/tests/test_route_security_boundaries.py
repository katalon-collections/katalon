# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Structural authorization-boundary tests (katalon issue #382).

Two invariants that matter more than generic DAST scanning for "who can get
into the admin API and what can an anonymous portal visitor do":

1. Every `/v1/*` operation must declare a security requirement (OAuth2
   bearer, API key, or the refresh cookie) — i.e. nobody reaches admin
   functionality without presenting *some* credential. Enforced today via
   router-level ``dependencies=[Depends(get_current_user)]`` in
   ``main.py``; this test fails the moment a future route is mounted
   without it, without anyone having to remember to hand-list the new
   route.
2. Every `/portal/v1/*` operation is read-only (GET/HEAD, plus the one
   documented read-via-POST search endpoint) — the public, unauthenticated
   API can structurally never expose a write.

Both read FastAPI's own generated OpenAPI schema (`app.openapi()`), which
already carries accurate per-operation security metadata — no live HTTP
calls, no database, runs in milliseconds as part of the fast unit suite.
This complements, not replaces, the hand-picked route checks in
`test_security_policies.py` (those assert the *effect* — 403 for the wrong
role — for a curated sample; this asserts the *shape* — every route,
automatically, forever).
"""

from __future__ import annotations

from katalon.main import app

# Endpoints intentionally reachable without any credential: obtaining the
# first token, and the two password-reset steps (which are unauthenticated
# by definition — that's how you regain access without one).
PUBLIC_V1_ENDPOINTS = {
    ("post", "/v1/auth/token"),
    ("post", "/v1/auth/password-reset"),
    ("post", "/v1/auth/password-reset/confirm"),
    # Public-media direct-by-ID routes (media.py internal_router, mounted
    # without the router-level auth dependency): anonymous access is
    # deliberate for publicly visible media, enforced per-request inside
    # serve_media_by_id via ensure_publicly_visible() + media.is_public/
    # status=="ready" checks, not by a missing credential requirement.
    ("get", "/v1/media/{media_id}/file"),
    ("get", "/v1/media/{media_id}/download"),
}

# Portal search takes a complex filter payload and is a read, not a write;
# it is the one legitimate POST in the public portal API.
PORTAL_READ_VIA_POST = {"/portal/v1/search/advanced"}
_SAFE_METHODS = {"get", "head"}


def _operations(paths: dict, prefix: str) -> list[tuple[str, str, dict]]:
    return [
        (method, path, operation)
        for path, methods in paths.items()
        if path.startswith(prefix)
        for method, operation in methods.items()
        if method in {"get", "post", "put", "patch", "delete"}
    ]


def test_every_v1_route_requires_a_credential() -> None:
    schema = app.openapi()
    unprotected = [
        f"{method.upper()} {path}"
        for method, path, operation in _operations(schema["paths"], "/v1/")
        if not operation.get("security") and (method, path) not in PUBLIC_V1_ENDPOINTS
    ]
    assert unprotected == [], (
        "These /v1 routes declare no security requirement — anyone can call them "
        f"without logging in: {unprotected}. If this is intentional, add the route "
        "to PUBLIC_V1_ENDPOINTS with a comment explaining why."
    )


def test_portal_router_exposes_no_write_endpoints() -> None:
    schema = app.openapi()
    writes = [
        f"{method.upper()} {path}"
        for method, path, operation in _operations(schema["paths"], "/portal/v1/")
        if method not in _SAFE_METHODS and path not in PORTAL_READ_VIA_POST
    ]
    assert writes == [], (
        f"These public portal routes are not GET/HEAD: {writes}. The unauthenticated "
        "portal API must stay read-only — if this is a genuine read encoded as POST "
        "(like search/advanced), add it to PORTAL_READ_VIA_POST with a comment."
    )
