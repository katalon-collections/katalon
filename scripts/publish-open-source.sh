#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Karl Krägelin

set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 vMAJOR.MINOR.0 OUTPUT_DIRECTORY" >&2
  exit 64
fi

tag=$1
output_dir=$2

case $output_dir in
  /*) ;;
  *) output_dir="$PWD/$output_dir" ;;
esac

repo_root=$(git -C "$(dirname "$0")/.." rev-parse --show-toplevel)
cd "$repo_root"

if [[ ! $tag =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Invalid release tag: $tag" >&2
  exit 64
fi

patch=${tag##*.}
if [[ $patch != 0 && ${PUBLISH_PATCH_RELEASE:-} != 1 ]]; then
  echo "Only minor-release tags may be published automatically: $tag" >&2
  exit 64
fi

git rev-parse --verify --quiet "${tag}^{commit}" >/dev/null || {
  echo "Unknown release tag: $tag" >&2
  exit 64
}

if [[ -e $output_dir ]] && [[ -n $(find "$output_dir" -mindepth 1 -maxdepth 1 ! -name .git -print -quit) ]]; then
  echo "Output directory must be empty: $output_dir" >&2
  exit 64
fi

mkdir -p "$output_dir"
staging_dir=$(mktemp -d)
trap 'rm -rf "$staging_dir"' EXIT

git archive "$tag" | tar -x -C "$staging_dir"

copy_path() {
  local path=$1
  [[ -e "$staging_dir/$path" ]] || return 0
  mkdir -p "$output_dir/$(dirname "$path")"
  cp -a "$staging_dir/$path" "$output_dir/$path"
}

for path in backend docker e2e frontend media; do
  copy_path "$path"
done

for path in scripts/gen_openapi.py scripts/gen_release_metadata.py; do
  copy_path "$path"
done

for path in \
  .dockerignore \
  .gitignore \
  CHANGELOG.md \
  DISCLAIMER.md \
  LICENSE \
  Makefile \
  README.md \
  SECURITY.md \
  docker-compose.cantaloupe.yml \
  docker-compose.dev.yml \
  docker-compose.override.yml.example \
  docker-compose.prod.yml \
  docker-compose.yml \
  install.sh \
  openapi.json \
  pyproject.toml \
  release-meta.toml \
  uv.lock; do
  copy_path "$path"
done

mkdir -p "$output_dir/.github/workflows"
cp "$staging_dir/.github/workflows/public-container-images.yml" \
  "$output_dir/.github/workflows/container-images.yml"

public_release_tags="${PUBLIC_RELEASE_TAGS:+${PUBLIC_RELEASE_TAGS},}${tag}"
awk -v public_tags="$public_release_tags" '
  BEGIN {
    split(public_tags, tags, ",")
    for (i in tags) public[tags[i]] = 1
  }
  /^## \[Unreleased\]/ {
    print
    include = 0
    next
  }
  /^## \[[0-9]+\.[0-9]+\.[0-9]+\]/ {
    version = $2
    gsub(/^\[|\]$/, "", version)
    include = public["v" version]
  }
  include || !seen_release { print }
  /^## \[[0-9]+\.[0-9]+\.[0-9]+\]/ { seen_release = 1 }
' "$output_dir/CHANGELOG.md" > "$output_dir/CHANGELOG.public.md"
mv "$output_dir/CHANGELOG.public.md" "$output_dir/CHANGELOG.md"

for path in .agents .claude .codegraph almanac charts AGENTS.md CLAUDE.md DESIGN.json DESIGN.md KONZEPT.md features.json scc_report.txt; do
  if [[ -e "$output_dir/$path" ]]; then
    echo "Forbidden public-export path: $path" >&2
    exit 1
  fi
done

version=${tag#v}
grep -q "^version = \"${version}\"$" "$output_dir/backend/pyproject.toml"
grep -q "\"version\": \"${version}\"" "$output_dir/frontend/admin/package.json"
grep -q "\"version\": \"${version}\"" "$output_dir/frontend/portal/package.json"
