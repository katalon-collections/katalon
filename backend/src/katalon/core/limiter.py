# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Shared slowapi limiter.

`get_remote_address` reads `request.client.host`. Behind nginx that is only the
real client when uvicorn's ProxyHeadersMiddleware has rewritten it from
`X-Forwarded-For`, which requires the proxy to be trusted via
`FORWARDED_ALLOW_IPS` (set in docker/Dockerfile.backend). Without that every
request shares one bucket keyed on the nginx container IP, so a single crawler
locks out all visitors.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from katalon.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[lambda: settings.rate_limit_default],
    storage_uri=settings.rate_limit_storage_uri or None,
    # Fail open: a Redis outage must not turn every public request into a 500.
    # Same posture as /health, which deliberately does not check Redis.
    swallow_errors=True,
)
