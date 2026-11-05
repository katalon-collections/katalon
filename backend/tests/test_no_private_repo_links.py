# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Shipped code must not point users or remote services at the private maintainer repo."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SHIPPED_DIRS = [
    REPO_ROOT / "backend" / "src",
    REPO_ROOT / "frontend" / "admin" / "src",
    REPO_ROOT / "frontend" / "portal" / "src",
]
SUFFIXES = {".py", ".ts", ".tsx", ".json", ".html", ".css"}


def test_shipped_code_has_no_private_repo_links() -> None:
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for base in SHIPPED_DIRS
        if base.exists()
        for path in base.rglob("*")
        if path.suffix in SUFFIXES
        and "node_modules" not in path.parts
        and "github.com/karkraeg" in path.read_text(encoding="utf-8", errors="ignore").lower()
    ]
    assert offenders == []
