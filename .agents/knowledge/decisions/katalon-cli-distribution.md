---
type: Decision
title: "katalon-cli Distribution"
tags: [architecture, documentation]
timestamp: 2026-10-30T00:00:00Z
origin: almanac/decisions/operations/katalon-cli-distribution.md
consolidated: 2026-10-30
---

Production Katalon instances are installed and updated with `katalon-cli`, a separate Python package (`uv tool install katalon-cli`) whose public repository is `katalon-collections/katalon-cli`. The CLI pulls versioned release images and manages an instance directory instead of requiring operators to clone the `Katalon` source repo [1] [2].

## Context

`install.sh` in this repo builds the stack from local source (`make up`) [5]. That fits development and production-like testing of this checkout, but it means operators need the full source repo, a build toolchain, and manual version tracking to run and update a real instance [1].

## Decision

`katalon-cli` is its own repo and PyPI package, distributed via `uv tool install` rather than a Go binary; operators who can run Docker can run one `curl | sh` for `uv`, and the CLI can share Pydantic schemas with the backend if useful later [2].

It manages a production instance directory (default: `/opt/katalon` on Linux, `~/katalon` on macOS) containing a generated `compose.yaml`, `.env`, and `installation.json` (the single source of truth for the installed version). `katalon update` always backs up (`pg_dump` + `.env` + `installation.json`) before pulling new images and running migrations; `katalon rollback` restores that backup rather than attempting `alembic downgrade`, since downgrades are often undefined or unsafe [2].

This repo's only obligation to that CLI is publishing a `katalon-release.json` asset on each GitHub Release. `scripts/gen_release_metadata.py` generates it: `version` and `migration_required` are derived automatically (version from `backend/pyproject.toml`, `migration_required` from new files under `backend/migrations/versions/` since the previous tag); `compose_revision`, `minimum_installer_version`, `images` (exact images of the third-party services), and `requires` (Postgres/Elasticsearch version constraints) as well as environment variable metadata (`env_vars`, `deprecated_env_vars`) are maintained in `release-meta.toml`, release definitions, or changelog metadata [3] [4]. A `.github/workflows/release-metadata.yml` job attaches the generated file to the release on every `vX.Y.Z` tag push [7].

The Katalon release, not the CLI, decides which third-party images an instance runs. `[images]` in `release-meta.toml` names Postgres, Redis, Elasticsearch, Cantaloupe, nginx, and Caddy as `repository:tag`; katalon-cli renders them into `compose.yaml` on install, update, and rollback and pulls them with the Katalon images [4] [2]. `docker-compose.yml` and `charts/katalon/values.yaml` must use the same images, and the images must satisfy `requires`; `backend/tests/test_release_metadata.py` enforces both [3]. `requires` states the versions Katalon technically supports, which matters when an operator swaps an image via `compose.override.yaml`: before changing anything, `katalon update` compares the effective images (base plus override) before and after, aborts if Postgres or Elasticsearch would change major version (Postgres needs dump/restore, Elasticsearch cannot open a data directory of another major) or if an image violates `requires` [2]. Releases up to 1.46.0 carry no `images`; the CLI falls back to the images its template had until 0.3.5 and does not enforce their `requires`, which was never checked and said Elasticsearch `>=8.15` while every stack ran 8.13.4 [2].

The current release metadata sets `compose_revision = 3` and `minimum_installer_version = "0.4.0"`: the template must know the Cantaloupe derivative-cache layout (0.3.0), and older CLIs would ignore `images` and silently render their built-in versions (0.4.0) [4].

TLS is handled by `katalon-cli`, not this repo: the install wizard offers a standalone mode (bundled Caddy, automatic Let's Encrypt) or a behind-existing-reverse-proxy mode, chosen from the `KATALON_BASE_URL` the operator provides [2].

## Consequences

The dev workflow (`docker-compose.dev.yml`, `install.sh`, `.agents/DEV.md`) is unaffected — it keeps building from source [5]. Production installs instead depend on GHCR release images existing. The public image workflow on `katalon-collections/katalon` builds and scans the API, worker, Admin, and Portal images for each `v*` tag, then pushes each image only after its Trivy gate passes [6].

Anyone changing `docker-compose.yml` service topology, ports, or volumes in a way that a generated `compose.yaml` would need to mirror must change the CLI template and bump `compose_revision` and `minimum_installer_version` in `release-meta.toml`; `katalon-cli` re-renders `compose.yaml` on every update and reports a compose-revision change [4] [2]. A new image version for an existing service needs only `[images]` plus the matching `docker-compose.yml` and Helm values [4].

Public source publication is also a curated export, not a raw mirror of the private repo. `.github/workflows/publish-public-release.yml` validates private tags on `karkraeg/Katalon`, clones `katalon-collections/katalon`, replaces its tree with the curated export, commits there, and creates the public tag from that public commit [8] [9]. Automatic public publication only runs for minor tags ending in `.0`; patch tags require `workflow_dispatch`, which sets `PUBLISH_PATCH_RELEASE=1` for the export guard [8] [9]. `scripts/publish-open-source.sh` copies `CHANGELOG.public.md` to the public repository as `CHANGELOG.md` instead of filtering the private technical changelog [9]. `CHANGELOG.public.md` is curated end-user text with new features and, from 1.49.0, bug fixes (no internal refactorings, CI/test changes or pure documentation); `AGENTS.md` makes updating it part of the release steps before a public minor release [10] [11].

# Citations

[1] https://github.com/karkraeg/Katalon/issues/286
[2] https://github.com/katalon-collections/katalon-cli
[3] scripts/gen_release_metadata.py
[4] release-meta.toml
[5] install.sh
[6] .github/workflows/public-container-images.yml
[7] .github/workflows/release-metadata.yml
[8] .github/workflows/publish-public-release.yml
[9] scripts/publish-open-source.sh
[10] CHANGELOG.public.md
[11] AGENTS.md
