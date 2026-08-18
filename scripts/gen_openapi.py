#!/usr/bin/env python3
"""Generate a static OpenAPI schema for the Katalon API.

Usage:

    python scripts/gen_openapi.py [OUTPUT_PATH]

Defaults to writing openapi.json in the repository root.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _set_minimal_env() -> None:
    """Set dummy values for required settings so the app can be imported."""
    defaults = {
        "SECRET_KEY": "openapi-gen-secret-key-must-be-32-characters-long",
        "KATALON_SECRETS_KEY": "openapi-gen-katalon-secrets-key-32-chars",
        "DATABASE_URL": "postgresql+asyncpg://x:x@localhost:1/x",
        "REDIS_URL": "redis://localhost:1/0",
        "ELASTICSEARCH_URL": "http://localhost:1",
        "CANTALOUPE_URL": "http://localhost:1",
        "CANTALOUPE_PUBLIC_URL": "http://localhost",
        "KATALON_BASE_URL": "http://localhost",
        "DEBUG": "false",
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else repo_root / "openapi.json"

    _set_minimal_env()
    sys.path.insert(0, str(repo_root / "backend" / "src"))

    from fastapi.openapi.utils import get_openapi
    from katalon.main import app

    schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
    )

    # Remove internal debug-only mock endpoints from the published schema.
    paths = schema.get("paths", {})
    for path in list(paths.keys()):
        if path.startswith("/v1/dnb-urn-mock"):
            del paths[path]

    output_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(schema.get('paths', {}))} paths to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
