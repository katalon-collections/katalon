---
title: "katalon-cli Distribution"
summary: "Production installs use a separate Python CLI (katalon-cli) that pulls pinned release images, not a source-repo checkout or the dev docker-compose stack."
topics: [decisions, operations, deployment, installer]
sources:
  - id: issue
    type: web
    url: https://github.com/karkraeg/Katalon/issues/286
  - id: cli-repo
    type: web
    url: https://github.com/katalon-collections/katalon-cli
  - id: release-script
    type: file
    path: scripts/gen_release_metadata.py
  - id: release-meta
    type: file
    path: release-meta.toml
  - id: install-sh
    type: file
    path: install.sh
---

Production Katalon instances are installed and updated with `katalon-cli`, a separate Python package (`uv tool install katalon-cli`) whose public repository is `katalon-collections/katalon-cli`. The CLI pulls versioned release images and manages an instance directory instead of requiring operators to clone the `Katalon` source repo [@issue] [@cli-repo].

## Context

`install.sh` in this repo builds the stack from local source (`make up`) [@install-sh]. That fits development and production-like testing of this checkout, but it means operators need the full source repo, a build toolchain, and manual version tracking to run and update a real instance [@issue].

## Decision

`katalon-cli` is its own repo and PyPI package, distributed via `uv tool install` rather than a Go binary; operators who can run Docker can run one `curl | sh` for `uv`, and the CLI can share Pydantic schemas with the backend if useful later [@cli-repo].

It manages a production instance directory (default: `/opt/katalon` on Linux, `~/katalon` on macOS) containing a generated `compose.yaml`, `.env`, and `installation.json` (the single source of truth for the installed version). `katalon update` always backs up (`pg_dump` + `.env` + `installation.json`) before pulling new images and running migrations; `katalon rollback` restores that backup rather than attempting `alembic downgrade`, since downgrades are often undefined or unsafe [@cli-repo].

This repo's only obligation to that CLI is publishing a `katalon-release.json` asset on each GitHub Release. `scripts/gen_release_metadata.py` generates it: `version` and `migration_required` are derived automatically (version from `backend/pyproject.toml`, `migration_required` from new files under `backend/migrations/versions/` since the previous tag); `compose_revision`, `minimum_installer_version`, and `requires` (Postgres/Elasticsearch version constraints) are manually maintained in `release-meta.toml` since they only change when compose topology or CLI requirements actually change [@release-script] [@release-meta]. A `.github/workflows/release-metadata.yml` job attaches the generated file to the release on every `vX.Y.Z` tag push.

TLS is handled by `katalon-cli`, not this repo: the install wizard offers a standalone mode (bundled Caddy, automatic Let's Encrypt) or a behind-existing-reverse-proxy mode, chosen from the `KATALON_BASE_URL` the operator provides [@cli-repo].

## Consequences

The dev workflow (`docker-compose.dev.yml`, `install.sh`, `.agents/DEV.md`) is unaffected — it keeps building from source [@install-sh]. Production installs instead depend on `ghcr.io/karkraeg/katalon-{api,web,cantaloupe}` images existing, which as of this writing are not yet published by any CI workflow in this repo; that gap must close before `katalon-cli install` can complete against a real release.

Anyone changing `docker-compose.yml` service topology, ports, or volumes in a way that a generated `compose.yaml` would need to mirror must bump `compose_revision` in `release-meta.toml` — `katalon-cli` treats a compose-revision mismatch as a signal to re-render the instance's `compose.yaml` on update [@release-meta] [@cli-repo].
