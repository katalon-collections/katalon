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
  - id: public-image-workflow
    type: file
    path: .github/workflows/public-container-images.yml
  - id: release-metadata-workflow
    type: file
    path: .github/workflows/release-metadata.yml
  - id: public-release-workflow
    type: file
    path: .github/workflows/publish-public-release.yml
  - id: public-export-script
    type: file
    path: scripts/publish-open-source.sh
  - id: public-changelog
    type: file
    path: CHANGELOG.public.md
  - id: agents
    type: file
    path: AGENTS.md
  - id: decision-record
    type: file
    path: .agents/knowledge/decisions/katalon-cli-distribution.md
---

The authoritative rationale and decision status live in the OKF record
`.agents/knowledge/decisions/katalon-cli-distribution.md` [@decision-record]. This page summarizes the
choice and its implementation; update the OKF record first when changing the decision.


Production Katalon instances are installed and updated with `katalon-cli`, a separate Python package (`uv tool install katalon-cli`) whose public repository is `katalon-collections/katalon-cli`. The CLI pulls versioned release images and manages an instance directory instead of requiring operators to clone the `Katalon` source repo [@issue] [@cli-repo].


## Current Contract

`katalon-cli` is its own repo and PyPI package, distributed via `uv tool install` rather than a Go binary; operators who can run Docker can run one `curl | sh` for `uv`, and the CLI can share Pydantic schemas with the backend if useful later [@cli-repo].

It manages a production instance directory (default: `/opt/katalon` on Linux, `~/katalon` on macOS) containing a generated `compose.yaml`, `.env`, and `installation.json` (the single source of truth for the installed version). `katalon update` always backs up (`pg_dump` + `.env` + `installation.json`) before pulling new images and running migrations; `katalon rollback` restores that backup rather than attempting `alembic downgrade`, since downgrades are often undefined or unsafe [@cli-repo].

This repo's only obligation to that CLI is publishing a `katalon-release.json` asset on each GitHub Release. `scripts/gen_release_metadata.py` generates it: `version` and `migration_required` are derived automatically (version from `backend/pyproject.toml`, `migration_required` from new files under `backend/migrations/versions/` since the previous tag); `compose_revision`, `minimum_installer_version`, `images` (exact images of the third-party services), and `requires` (Postgres/Elasticsearch version constraints) as well as environment variable metadata (`env_vars`, `deprecated_env_vars`) are maintained in `release-meta.toml`, release definitions, or changelog metadata [@release-script] [@release-meta]. A `.github/workflows/release-metadata.yml` job attaches the generated file to the release on every `vX.Y.Z` tag push [@release-metadata-workflow].

The Katalon release, not the CLI, decides which third-party images an instance runs. `[images]` in `release-meta.toml` names Postgres, Redis, Elasticsearch, Cantaloupe, nginx, and Caddy as `repository:tag`; katalon-cli renders them into `compose.yaml` on install, update, and rollback and pulls them with the Katalon images [@release-meta] [@cli-repo]. `docker-compose.yml` and `charts/katalon/values.yaml` must use the same images, and the images must satisfy `requires`; `backend/tests/test_release_metadata.py` enforces both [@release-script]. `requires` states the versions Katalon technically supports, which matters when an operator swaps an image via `compose.override.yaml`: before changing anything, `katalon update` compares the effective images (base plus override) before and after, aborts if Postgres or Elasticsearch would change major version (Postgres needs dump/restore, Elasticsearch cannot open a data directory of another major) or if an image violates `requires` [@cli-repo]. Releases up to 1.46.0 carry no `images`; the CLI falls back to the images its template had until 0.3.5 and does not enforce their `requires`, which was never checked and said Elasticsearch `>=8.15` while every stack ran 8.13.4 [@cli-repo].

The current release metadata sets `compose_revision = 3` and `minimum_installer_version = "0.4.0"`: the template must know the Cantaloupe derivative-cache layout (0.3.0), and older CLIs would ignore `images` and silently render their built-in versions (0.4.0) [@release-meta].

TLS is handled by `katalon-cli`, not this repo: the install wizard offers a standalone mode (bundled Caddy, automatic Let's Encrypt) or a behind-existing-reverse-proxy mode, chosen from the `KATALON_BASE_URL` the operator provides [@cli-repo].

## Implementation Constraints

The dev workflow (`docker-compose.dev.yml`, `install.sh`, `.agents/DEV.md`) is unaffected — it keeps building from source [@install-sh]. Production installs instead depend on GHCR release images existing. The public image workflow on `katalon-collections/katalon` builds and scans the API, worker, Admin, and Portal images for each `v*` tag, then pushes each image only after its Trivy gate passes [@public-image-workflow].

Anyone changing `docker-compose.yml` service topology, ports, or volumes in a way that a generated `compose.yaml` would need to mirror must change the CLI template and bump `compose_revision` and `minimum_installer_version` in `release-meta.toml`; `katalon-cli` re-renders `compose.yaml` on every update and reports a compose-revision change [@release-meta] [@cli-repo]. A new image version for an existing service needs only `[images]` plus the matching `docker-compose.yml` and Helm values [@release-meta].

Public source publication is also a curated export, not a raw mirror of the private repo. `.github/workflows/publish-public-release.yml` validates private tags on `karkraeg/Katalon`, clones `katalon-collections/katalon`, replaces its tree with the curated export, commits there, and creates the public tag from that public commit [@public-release-workflow] [@public-export-script]. Automatic public publication only runs for minor tags ending in `.0`; patch tags require `workflow_dispatch`, which sets `PUBLISH_PATCH_RELEASE=1` for the export guard [@public-release-workflow] [@public-export-script]. `scripts/publish-open-source.sh` copies `CHANGELOG.public.md` to the public repository as `CHANGELOG.md` instead of filtering the private technical changelog [@public-export-script]. `CHANGELOG.public.md` is curated end-user text with new features and, from 1.49.0, bug fixes (no internal refactorings, CI/test changes or pure documentation); `AGENTS.md` makes updating it part of the release steps before a public minor release [@public-changelog] [@agents].
