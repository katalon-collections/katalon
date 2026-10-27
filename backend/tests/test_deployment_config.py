# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

"""Guards for deployment files that have no runtime test of their own."""

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def _compose() -> dict:
    return yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text())


def test_cantaloupe_cache_survives_restarts_on_disk() -> None:
    services = _compose()["services"]
    cantaloupe = services["cantaloupe"]
    volumes = [v for v in cantaloupe["volumes"] if isinstance(v, str)]
    assert "${CANTALOUPE_CACHE_DIR:-cantaloupe_cache}:/data" in volumes
    assert "cantaloupe_cache" in _compose()["volumes"]
    env = cantaloupe["environment"]
    assert "CANTALOUPE_FILESYSTEMCACHE_PATHNAME=${CANTALOUPE_FILESYSTEMCACHE_PATHNAME:-/data/cache}" in env
    assert "CANTALOUPE_CACHE_SERVER_WORKER_ENABLED=true" in env
    # Ownership is fixed before Cantaloupe starts, for any volume or bind directory.
    assert cantaloupe["depends_on"]["cantaloupe-cache-init"]["condition"] == (
        "service_completed_successfully"
    )
    assert "chown cantaloupe:cantaloupe" in " ".join(services["cantaloupe-cache-init"]["entrypoint"])


def test_cantaloupe_tmpfs_option_has_octal_1777_mode() -> None:
    tmpfs = next(
        v for v in _compose()["services"]["cantaloupe"]["volumes"]
        if isinstance(v, dict) and v.get("type") == "tmpfs"
    )
    # Compose reads `mode` as a decimal integer: 1023 == 0o1777.
    assert tmpfs["tmpfs"]["mode"] == 0o1777


def test_cantaloupe_healthcheck_writes_to_configured_cache() -> None:
    test = _compose()["services"]["cantaloupe"]["healthcheck"]["test"][1]
    assert "runuser -u cantaloupe" in test
    assert "CANTALOUPE_FILESYSTEMCACHE_PATHNAME:-/data/cache" in test


def test_portal_thumbnail_sizes_match_backend() -> None:
    """The warm-up task pre-renders exactly the sizes the portal requests."""
    import re

    from katalon.core.thumbnails import THUMBNAIL_HEIGHT, THUMBNAIL_HEIGHT_HIDPI

    source = (REPO_ROOT / "frontend/portal/src/utils/thumbnails.ts").read_text()
    assert re.search(rf"THUMBNAIL_HEIGHT = {THUMBNAIL_HEIGHT}\b", source)
    assert re.search(rf"THUMBNAIL_HEIGHT_HIDPI = {THUMBNAIL_HEIGHT_HIDPI}\b", source)


def test_nginx_iiif_cache_control_follows_media_visibility() -> None:
    for name in ("docker/nginx.conf", "docker/nginx.dev.conf"):
        conf = (REPO_ROOT / name).read_text()
        block = conf[conf.index("location /iiif/ {"):]
        block = block[: block.index("\n    }\n")]
        assert "auth_request_set $media_visibility $upstream_http_x_media_visibility;" in block
        assert "proxy_hide_header Cache-Control;" in block
        assert "add_header Cache-Control $iiif_cache_control;" in block
        # A location-level add_header drops the server-level security headers.
        assert 'add_header X-Content-Type-Options "nosniff" always;' in block
        assert 'public  "public, max-age=2592000";' in conf


def test_cantaloupe_never_marks_derivatives_public_itself() -> None:
    env = _compose()["services"]["cantaloupe"]["environment"]
    assert "CANTALOUPE_CACHE_CLIENT_PUBLIC=false" in env
    assert "CANTALOUPE_CACHE_CLIENT_PRIVATE=true" in env


def test_record_uri_location_keeps_security_headers() -> None:
    """The content-negotiated record URI location adds Vary; without repeating them,
    it would serve the portal shell without CSP/HSTS & co."""
    for name in ("docker/nginx.conf", "docker/nginx.dev.conf"):
        conf = (REPO_ROOT / name).read_text()
        start = conf.index('add_header Vary "Accept, User-Agent" always;')
        block = conf[start: conf.index("\n    }\n", start)]
        assert "add_header Content-Security-Policy" in block
        assert 'add_header X-Frame-Options "SAMEORIGIN" always;' in block


def _nginx_blocks(text: str) -> dict:
    """Minimal nginx parser: nested blocks with the header names they add."""
    import re

    text = re.sub(r"#[^\n]*", "", text)
    text = re.sub(r'"[^"]*"|\'[^\']*\'', lambda m: re.sub(r"[{};]", "_", m.group()), text)
    root: dict = {"name": "file", "line": 0, "headers": [], "children": []}
    stack = [root]
    pos = 0
    for match in re.finditer(r"[{};]", text):
        chunk = text[pos:match.start()].strip()
        if match.group() == "{":
            node = {"name": " ".join(chunk.split()), "line": text.count("\n", 0, match.start()) + 1,
                    "headers": [], "children": []}
            stack[-1]["children"].append(node)
            stack.append(node)
        elif match.group() == ";":
            parts = chunk.split()
            if parts and parts[0] == "add_header":
                stack[-1]["headers"].append(parts[1].lower())
        else:
            stack.pop()
        pos = match.end()
    return root


def _dropped_headers(node: dict, inherited: list[str], found: list[str]) -> list[str]:
    if node["headers"] and inherited:
        missing = sorted(set(inherited) - set(node["headers"]))
        if missing:
            found.append(f"line {node['line']} {node['name'][:50]}: {', '.join(missing)}")
    for child in node["children"]:
        _dropped_headers(child, node["headers"] or inherited, found)
    return found


@pytest.mark.parametrize("name", sorted(p.name for p in (REPO_ROOT / "docker").glob("nginx*.conf")))
def test_no_nginx_block_drops_inherited_security_headers(name: str) -> None:
    """nginx: a block with its own add_header inherits none from the outer level, so
    every such block must repeat the server-level headers (CSP, HSTS, ...)."""
    root = _nginx_blocks((REPO_ROOT / "docker" / name).read_text())
    assert _dropped_headers(root, [], []) == []


def test_celery_concurrency_is_configurable() -> None:
    from katalon.config import Settings
    from katalon.workers.celery_app import celery_app, settings

    assert celery_app.conf.worker_concurrency == settings.celery_concurrency
    assert Settings(celery_concurrency="3").celery_concurrency == 3
    # Compose hands an unset variable over as an empty string: Celery default.
    assert Settings(celery_concurrency="").celery_concurrency is None
    assert "CELERY_CONCURRENCY" in _compose()["services"]["worker"]["environment"]


def test_cantaloupe_image_is_pinned_and_quiet() -> None:
    """`:main` moves under existing installations; the image's own log level is debug."""
    services = _compose()["services"]
    for name in ("cantaloupe", "cantaloupe-cache-init"):
        image = services[name]["image"]
        assert image.startswith("islandora/cantaloupe:") and not image.endswith(":main"), name
    assert services["cantaloupe"]["image"] == services["cantaloupe-cache-init"]["image"]
    env = services["cantaloupe"]["environment"]
    assert "CANTALOUPE_LOG_APPLICATION_LEVEL=${CANTALOUPE_LOG_LEVEL:-info}" in env
    assert "CANTALOUPE_LOG_ACCESS_CONSOLEAPPENDER_ENABLED=false" in env
    chart = yaml.safe_load((REPO_ROOT / "charts/katalon/values.yaml").read_text())
    assert chart["cantaloupe"]["image"] == services["cantaloupe"]["image"]


def test_cantaloupe_memory_limit_leaves_room_for_heap() -> None:
    env = _compose()["services"]["cantaloupe"]["environment"]
    assert "CANTALOUPE_HEAP_MAX=${CANTALOUPE_HEAP_MAX:-1g}" in env
    # The prod override uses Compose's !reset tag, which safe_load rejects.
    prod = (REPO_ROOT / "docker-compose.prod.yml").read_text()
    cantaloupe = prod.split("\n  cantaloupe:\n", 1)[1].split("\n  api:\n", 1)[0]
    assert "memory: ${CANTALOUPE_MEMORY_LIMIT:-1536m}" in cantaloupe
