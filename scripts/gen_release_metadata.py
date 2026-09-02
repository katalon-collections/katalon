#!/usr/bin/env python3
"""Generiert katalon-release.json für ein Release-Tag (katalon-cli Issue #286).

Version + migration_required/breaking werden automatisch ermittelt,
compose_revision/minimum_installer_version/requires kommen aus release-meta.toml
(manuell gepflegt, s. Kommentar dort).

Usage: scripts/gen_release_metadata.py [--tag vX.Y.Z] [--out katalon-release.json]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def run(*args: str) -> str:
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout.strip()


def current_version(tag: str | None) -> str:
    if tag:
        return tag.lstrip("v")
    match = re.search(r'^version\s*=\s*"([^"]+)"', (REPO_ROOT / "backend/pyproject.toml").read_text(), re.M)
    if not match:
        raise SystemExit("Version nicht in backend/pyproject.toml gefunden.")
    return match.group(1)


def previous_tag(current_tag: str) -> str | None:
    tags = run("git", "tag", "--sort=-v:refname").splitlines()
    tags = [t for t in tags if t != current_tag]
    return tags[0] if tags else None


def migration_required(current_tag: str, prev_tag: str | None) -> bool:
    if prev_tag is None:
        return True  # erstes Release: Migrationen sind neu ggü. "nichts"
    diff = run(
        "git", "diff", "--name-only", f"{prev_tag}..{current_tag}",
        "--", "backend/migrations/versions/",
    )
    return bool(diff.strip())


def is_breaking(version: str) -> bool:
    changelog = (REPO_ROOT / "CHANGELOG.md").read_text()
    section = re.search(
        rf"^## \[{re.escape(version)}\].*?(?=^## \[|\Z)", changelog, re.M | re.S
    )
    if not section:
        return False
    return "### Breaking" in section.group(0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", help="Release-Tag, z.B. v0.11.0. Default: aktueller git-Tag von HEAD.")
    parser.add_argument("--out", default="katalon-release.json")
    args = parser.parse_args()

    tag = args.tag or run("git", "describe", "--tags", "--exact-match")
    version = current_version(tag)
    prev = previous_tag(tag)

    meta = tomllib.loads((REPO_ROOT / "release-meta.toml").read_text())

    payload = {
        "version": version,
        "minimum_installer_version": meta["minimum_installer_version"],
        "migration_required": migration_required(tag, prev),
        "breaking": is_breaking(version),
        "compose_revision": meta["compose_revision"],
        "requires": meta["requires"],
    }

    Path(args.out).write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2), file=sys.stderr)


if __name__ == "__main__":
    main()
