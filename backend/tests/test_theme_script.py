# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

import json

import pytest

from katalon.api.v1 import theme


@pytest.mark.parametrize(
    ("script", "kept"),
    [
        ("custom.js", True),
        ("js/custom.js", True),
        ("../other/evil.js", False),
        ("/etc/evil.js", False),
        ("https://cdn.example/x.js", False),
        ("custom.css", False),
        (42, False),
    ],
)
@pytest.mark.asyncio
async def test_theme_script_paths_are_validated(tmp_path, monkeypatch, script, kept) -> None:
    media = tmp_path / "media"
    media.mkdir()
    theme_dir = tmp_path / "themes" / "bpk"
    theme_dir.mkdir(parents=True)
    (theme_dir / "theme.json").write_text(json.dumps({"name": "BPK", "script": script}))
    monkeypatch.setattr(theme.settings, "media_root", str(media))
    monkeypatch.setattr(theme.settings, "portal_theme", "bpk", raising=False)

    body = json.loads((await theme.get_theme()).body)

    assert body["directory"] == "bpk"
    assert ("script" in body) is kept
