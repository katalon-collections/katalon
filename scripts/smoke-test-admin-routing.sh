#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin
#
# VITE_BASE_PATH (baked into the admin image at build time) and the nginx
# /admin/ vs. / routing (docker/nginx.conf) are two independent configs with
# nothing enforcing they stay in sync. If they drift, admin JS/CSS requests
# silently fall through to the portal's SPA index.html (text/html instead of
# application/javascript) — no build error, no crash, just a white screen.
#
# Boots the real admin+portal images behind the real docker/nginx.conf
# (api/db/es/redis are not needed: nginx resolves upstreams lazily, and we
# only exercise the /admin/ and / locations) and checks that the admin
# entrypoint's JS asset is actually served as JavaScript through nginx.
#
# Usage: scripts/smoke-test-admin-routing.sh <admin-image> <portal-image>

set -euo pipefail

ADMIN_IMAGE="${1:?usage: $0 <admin-image> <portal-image>}"
PORTAL_IMAGE="${2:?usage: $0 <admin-image> <portal-image>}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NET="katalon-smoke-$$"
NGINX_PORT=18080

cleanup() {
  docker rm -f smoke-admin smoke-portal smoke-nginx smoke-api >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT

if [[ ! -f "$ROOT_DIR/docker/certs/localhost.crt" ]]; then
  mkdir -p "$ROOT_DIR/docker/certs"
  openssl req -x509 -nodes -newkey rsa:2048 \
    -keyout "$ROOT_DIR/docker/certs/localhost.key" -out "$ROOT_DIR/docker/certs/localhost.crt" -days 1 \
    -subj "/CN=localhost" -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
fi

docker network create "$NET" >/dev/null

# admin's and portal's own internal nginx (docker/nginx.admin.conf,
# docker/nginx.portal.conf) proxy_pass /v1/ to a literal "api:8000" upstream
# and resolve that hostname eagerly at startup — with nothing named "api" in
# the network, both containers refuse to start at all. A reachable
# nginx:alpine stub is enough; we never exercise /v1/ in this test.
docker run -d --name smoke-api --network "$NET" --network-alias api nginx:alpine >/dev/null

docker run -d --name smoke-admin --network "$NET" --network-alias admin "$ADMIN_IMAGE" >/dev/null
docker run -d --name smoke-portal --network "$NET" --network-alias portal "$PORTAL_IMAGE" >/dev/null
docker run -d --name smoke-nginx --network "$NET" -p "${NGINX_PORT}:80" \
  -v "$ROOT_DIR/docker/nginx.conf:/etc/nginx/conf.d/default.conf:ro" \
  -v "$ROOT_DIR/docker/certs:/etc/nginx/certs:ro" \
  nginx:alpine >/dev/null

for i in $(seq 1 30); do
  curl -sf "http://127.0.0.1:${NGINX_PORT}/admin/" >/dev/null 2>&1 && break
  sleep 1
  if [[ "$i" == 30 ]]; then
    echo "nginx never became reachable on /admin/" >&2
    docker logs smoke-nginx >&2 || true
    docker logs smoke-admin >&2 || true
    exit 1
  fi
done

admin_html="$(curl -sf "http://127.0.0.1:${NGINX_PORT}/admin/")"
asset_path="$(grep -oE '/admin/assets/[^"]+\.js' <<<"$admin_html" | head -1 || true)"

if [[ -z "$asset_path" ]]; then
  echo "Could not find an /admin/assets/*.js reference in /admin/ response — admin index.html:" >&2
  echo "$admin_html" >&2
  exit 1
fi

content_type="$(curl -sf -o /dev/null -w '%{content_type}' "http://127.0.0.1:${NGINX_PORT}${asset_path}")"

if [[ "$content_type" != *javascript* ]]; then
  echo "FAIL: ${asset_path} served as '${content_type}' instead of JavaScript." >&2
  echo "VITE_BASE_PATH and nginx /admin/ routing are out of sync." >&2
  exit 1
fi

echo "OK: ${asset_path} served as '${content_type}' via /admin/."
