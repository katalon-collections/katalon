#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml", "markdown"]
# ///
"""Render an OKF knowledge bundle to a static HTML site for local browsing.

Usage: uv run .agents/tools/okf_site.py <bundle-dir> <output-dir>
"""
import re
import shutil
import sys
from pathlib import Path

import markdown
import yaml

RESERVED = {"index.md", "log.md"}
LINK_RE = re.compile(r"\]\((?!https?://)([^)]*?)\)")

PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
</head>
<body>
<main class="container">
{meta}
{body}
</main>
</body>
</html>
"""


def split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    frontmatter = yaml.safe_load(parts[1]) or {}
    return frontmatter, parts[2].lstrip("\n")


def rewrite_target(target: str) -> str:
    if target.endswith("/"):
        return target + "index.html"
    if target.endswith(".md") or ".md#" in target:
        return target.replace(".md", ".html", 1)
    return target


def rewrite_links(body: str) -> str:
    return LINK_RE.sub(lambda m: f"]({rewrite_target(m.group(1))})", body)


def render_page(title: str, meta_html: str, body_md: str) -> str:
    html_body = markdown.markdown(rewrite_links(body_md), extensions=["tables", "fenced_code"])
    return PAGE.format(title=title, meta=meta_html, body=html_body)


def build(bundle_dir: Path, output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    for src in bundle_dir.rglob("*.md"):
        rel = src.relative_to(bundle_dir)
        dest = (output_dir / rel).with_suffix(".html")
        dest.parent.mkdir(parents=True, exist_ok=True)
        text = src.read_text(encoding="utf-8")

        if src.name in RESERVED:
            title = f"{rel.parent}/{src.name}" if rel.parent != Path(".") else src.name
            dest.write_text(render_page(title, "", text), encoding="utf-8")
            continue

        frontmatter, body = split_frontmatter(text)
        if not frontmatter.get("type"):
            print(f"skip (missing required 'type'): {rel}", file=sys.stderr)
            continue

        title = frontmatter.get("title") or src.stem
        meta_bits = [f"<strong>{frontmatter['type']}</strong>"]
        if frontmatter.get("tags"):
            meta_bits.append(", ".join(frontmatter["tags"]))
        if frontmatter.get("timestamp"):
            meta_bits.append(str(frontmatter["timestamp"]))
        meta_html = f"<p><small>{' &middot; '.join(meta_bits)}</small></p>"

        dest.write_text(render_page(title, meta_html, body), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    build(Path(sys.argv[1]), Path(sys.argv[2]))
