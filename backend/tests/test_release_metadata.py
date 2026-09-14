# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Add scripts directory to sys.path to import gen_release_metadata
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import gen_release_metadata as grm  # noqa: E402


def test_normalize_env_var_full():
    raw = {
        "key": "OIDC_CLIENT_ID",
        "description": "OAuth2 Client ID for SSO",
        "required": True,
        "secret": False,
        "default": "default-id",
    }
    result = grm.normalize_env_var(raw)
    assert result == {
        "key": "OIDC_CLIENT_ID",
        "description": "OAuth2 Client ID for SSO",
        "required": True,
        "secret": False,
        "default": "default-id",
    }


def test_normalize_env_var_defaults():
    raw = {"key": "NEW_FEATURE_FLAG"}
    result = grm.normalize_env_var(raw)
    assert result == {
        "key": "NEW_FEATURE_FLAG",
        "description": "",
        "required": False,
        "secret": False,
        "default": None,
    }


def test_normalize_env_var_missing_key():
    with pytest.raises(ValueError, match="ohne 'key'"):
        grm.normalize_env_var({"description": "missing key"})

    with pytest.raises(TypeError, match="Dict erwartet"):
        grm.normalize_env_var("not-a-dict")


def test_normalize_env_vars_deduplication():
    raw = [
        {"key": "VAR1", "description": "First definition"},
        {"key": "VAR2", "description": "Second var"},
        {"key": "VAR1", "description": "Duplicate definition"},
    ]
    result = grm.normalize_env_vars(raw)
    assert len(result) == 2
    assert result[0]["key"] == "VAR1"
    assert result[0]["description"] == "First definition"
    assert result[1]["key"] == "VAR2"


def test_normalize_deprecated_env_var():
    raw = {"key": "OLD_VAR", "note": "Replaced by NEW_VAR"}
    result = grm.normalize_deprecated_env_var(raw)
    assert result == {"key": "OLD_VAR", "note": "Replaced by NEW_VAR"}


def test_normalize_deprecated_env_var_missing_key():
    with pytest.raises(ValueError, match="ohne 'key'"):
        grm.normalize_deprecated_env_var({"note": "missing key"})


def test_parse_changelog_env_metadata_comment():
    changelog = """# Changelog

## [1.50.0] - 2026-10-01

<!-- release-metadata: {
  "env_vars": [
    {"key": "OIDC_CLIENT_ID", "description": "SSO Client ID", "required": false, "secret": false, "default": null}
  ],
  "deprecated_env_vars": [
    {"key": "OLD_AUTH_TOKEN", "note": "Replaced by OIDC"}
  ]
} -->

### Added
- Some feature
"""
    env_vars, dep_vars = grm.parse_changelog_env_metadata("1.50.0", changelog)
    assert len(env_vars) == 1
    assert env_vars[0]["key"] == "OIDC_CLIENT_ID"
    assert len(dep_vars) == 1
    assert dep_vars[0]["key"] == "OLD_AUTH_TOKEN"


def test_parse_changelog_env_metadata_markdown_sections():
    changelog = """# Changelog

## [1.50.0] - 2026-10-01

### Environment Variables
- `STORAGE_S3_KEY`: S3 access key (required, secret)
- `STORAGE_S3_BUCKET`: S3 bucket name (required, default: "katalon-media")
- `OLD_STORAGE_PATH` (deprecated): Ersetzt durch S3

### Deprecated Environment Variables
- `LEGACY_PROXY_URL`: Nicht mehr verwendet

### Added
- Feature
"""
    env_vars, dep_vars = grm.parse_changelog_env_metadata("1.50.0", changelog)
    assert len(env_vars) == 2
    assert env_vars[0]["key"] == "STORAGE_S3_KEY"
    assert env_vars[0]["required"] is True
    assert env_vars[0]["secret"] is True
    assert env_vars[1]["key"] == "STORAGE_S3_BUCKET"
    assert env_vars[1]["required"] is True
    assert env_vars[1]["default"] == "katalon-media"

    assert len(dep_vars) == 2
    dep_keys = {d["key"] for d in dep_vars}
    assert dep_keys == {"OLD_STORAGE_PATH", "LEGACY_PROXY_URL"}


def test_resolve_release_env_vars_cascade(tmp_path):
    # 1. Top-level in meta
    meta_top = {
        "compose_revision": 2,
        "minimum_installer_version": "0.1.0",
        "env_vars": [{"key": "TOP_VAR", "description": "from top level"}],
        "deprecated_env_vars": [{"key": "OLD_TOP", "note": "dep"}],
    }
    env, dep = grm.resolve_release_env_vars("1.0.0", meta_top, root=tmp_path)
    assert len(env) == 1 and env[0]["key"] == "TOP_VAR"
    assert len(dep) == 1 and dep[0]["key"] == "OLD_TOP"

    # 2. Version-specific in meta overrides top-level
    meta_versioned = {
        "compose_revision": 2,
        "minimum_installer_version": "0.1.0",
        "env_vars": [{"key": "TOP_VAR"}],
        "releases": {
            "1.0.0": {
                "env_vars": [{"key": "VERSIONED_VAR", "description": "versioned"}],
                "deprecated_env_vars": [],
            }
        },
    }
    env, dep = grm.resolve_release_env_vars("1.0.0", meta_versioned, root=tmp_path)
    assert len(env) == 1 and env[0]["key"] == "VERSIONED_VAR"
    assert len(dep) == 0

    # 3. Explicit definitions file overrides all
    def_file = tmp_path / "custom_def.json"
    def_file.write_text(
        json.dumps({
            "env_vars": [{"key": "EXPLICIT_VAR"}],
            "deprecated_env_vars": [{"key": "EXPLICIT_DEP", "note": "explicit"}],
        }),
        encoding="utf-8",
    )
    env, dep = grm.resolve_release_env_vars(
        "1.0.0", meta_versioned, definitions_source=def_file, root=tmp_path
    )
    assert len(env) == 1 and env[0]["key"] == "EXPLICIT_VAR"
    assert len(dep) == 1 and dep[0]["key"] == "EXPLICIT_DEP"

    # 4. Fallback when nothing specified
    empty_meta = {
        "compose_revision": 2,
        "minimum_installer_version": "0.1.0",
    }
    env, dep = grm.resolve_release_env_vars("1.0.0", empty_meta, root=tmp_path)
    assert env == []
    assert dep == []


def test_build_release_payload_structure(tmp_path):
    meta = {
        "compose_revision": 2,
        "minimum_installer_version": "0.1.0",
        "requires": {"postgres": ">=16"},
    }
    payload = grm.build_release_payload(
        tag="v1.30.0",
        version="1.30.0",
        meta=meta,
        root=tmp_path,
    )
    assert payload["version"] == "1.30.0"
    assert payload["minimum_installer_version"] == "0.1.0"
    assert payload["compose_revision"] == 2
    assert payload["requires"] == {"postgres": ">=16"}
    assert payload["env_vars"] == []
    assert payload["deprecated_env_vars"] == []
    assert "breaking" in payload
    assert "migration_required" in payload


def test_cli_execution_with_meta(tmp_path):
    meta_path = tmp_path / "release-meta.toml"
    meta_path.write_text(
        """
compose_revision = 3
minimum_installer_version = "0.2.0"

[requires]
postgres = ">=16"
elasticsearch = ">=8.15,<9"

[[env_vars]]
key = "CLI_TEST_VAR"
description = "Created for CLI test"
required = true
secret = false
default = "foo"

[[deprecated_env_vars]]
key = "CLI_OLD_VAR"
note = "replaced"
""",
        encoding="utf-8",
    )

    out_json = tmp_path / "katalon-release.json"
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "gen_release_metadata.py"),
        "--tag",
        "v2.0.0",
        "--meta-file",
        str(meta_path),
        "--out",
        str(out_json),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    assert res.returncode == 0
    assert out_json.exists()

    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["version"] == "2.0.0"
    assert data["compose_revision"] == 3
    assert data["minimum_installer_version"] == "0.2.0"
    assert len(data["env_vars"]) == 1
    assert data["env_vars"][0]["key"] == "CLI_TEST_VAR"
    assert data["env_vars"][0]["required"] is True
    assert data["env_vars"][0]["default"] == "foo"
    assert len(data["deprecated_env_vars"]) == 1
    assert data["deprecated_env_vars"][0]["key"] == "CLI_OLD_VAR"
