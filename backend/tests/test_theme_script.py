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


def test_theme_css_imports_stylesheet_and_layers_tokens() -> None:
    manifest = {
        "tokens": {"--accent": "#ac0634", "--header-bg": "#ffffff"},
        "fonts": {"body": "/themes/bpk/custom.css"},
    }

    css = theme.theme_css(manifest, {"--header-bg": "#eeeeee", "--fg": ""}, "#1e3a8a")

    assert css.startswith('@import url("/themes/bpk/custom.css");\n:root:root {')
    assert "--accent: #ac0634;" in css  # untouched default accent_color keeps the theme's
    assert "--header-bg: #eeeeee;" in css  # portal config color_tokens win
    assert "--fg: #181a1f;" in css  # empty override keeps the default
    assert "--accent: #00ff00;" in theme.theme_css(manifest, None, "#00ff00")


@pytest.mark.parametrize(
    "tokens",
    [
        {"--accent": "red; } body { display: none"},
        {"--accent": "red</style>"},
        {"accent": "red"},
        {"--accent": 3},
    ],
)
def test_theme_css_drops_tokens_that_leave_the_declaration(tokens) -> None:
    css = theme.theme_css({"tokens": tokens})
    assert "red" not in css
    assert css.count("{") == 1 and css.count("}") == 1


@pytest.mark.parametrize(
    "stylesheet",
    ["//evil.example/x.css", 'x.css");body{', "javascript:alert(1)", "http://plain.example/x.css"],
)
def test_theme_css_drops_invalid_stylesheets(stylesheet) -> None:
    assert "@import" not in theme.theme_css({"fonts": {"body": stylesheet}})
