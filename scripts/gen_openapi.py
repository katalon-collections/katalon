#!/usr/bin/env python3
"""Generate a static OpenAPI schema for the Katalon API.

Usage:

    python scripts/gen_openapi.py [OUTPUT_PATH] [--check]

Defaults to writing openapi.json in the repository root. ``--check`` validates
the generated schema and fails when the output file is stale.
"""

from __future__ import annotations

import argparse
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
    parser = argparse.ArgumentParser()
    parser.add_argument("output", nargs="?", type=Path, default=repo_root / "openapi.json")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    _set_minimal_env()
    sys.path.insert(0, str(repo_root / "backend" / "src"))

    from fastapi.openapi.models import OpenAPI
    from katalon.main import app

    schema = app.openapi()
    OpenAPI.model_validate(schema)
    rendered = json.dumps(schema, indent=2, ensure_ascii=False) + "\n"

    if args.check:
        if not args.output.exists() or args.output.read_text(encoding="utf-8") != rendered:
            print(f"{args.output} is stale; run scripts/gen_openapi.py")
            return 1
        print(f"Validated {len(schema.get('paths', {}))} paths in {args.output}")
        return 0

    args.output.write_text(rendered, encoding="utf-8")
    print(f"Wrote {len(schema.get('paths', {}))} paths to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
