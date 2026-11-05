---
title: "Backup And Restore"
summary: "How to use Katalon's database and media backups, run restore drills, and avoid destructive volume operations."
topics: [operations, backup, database, media]
sources:
  - id: backup-script
    type: file
    path: docker/backup.sh
  - id: production-doc
    type: file
    path: docs/02_produktion.md
  - id: upgrading-doc
    type: file
    path: docs/05_upgrading.md
  - id: migration-doc
    type: file
    path: docs/06_serverumzug.md
  - id: agent-rules
    type: file
    path: AGENTS.md
  - id: backup-drill-test
    type: file
    path: backend/tests/integration/test_backup_restore_drill.py
  - id: backup-drill-workflow
    type: file
    path: .github/workflows/backup-drill.yml
  - id: pg-restore-doc
    type: web
    url: https://www.postgresql.org/docs/16/app-pgrestore.html
---

Use this guide before deploying risky changes, repairing data problems, or proving backups can actually restore a Katalon instance. Katalon's durable data is split between PostgreSQL data, media files, `.env`, and instance overrides; Elasticsearch can be rebuilt from the database [@upgrading-doc] [@production-doc]. The successful outcome is a fresh `db_*.sql.gz` plus `media_*.tar.gz`, a known restore command, and no accidental deletion of database volumes.

## Know What Must Survive

Katalon stores records, schemas, vocabularies, authority source configuration, and other application data in the PostgreSQL volume, while media files live in the media mount configured by `MEDIA_ROOT` [@upgrading-doc]. The update guide states that `.env` and `docker-compose.override.yml` also live outside container images and must be preserved separately as instance configuration [@upgrading-doc].

Do not treat Elasticsearch as primary storage. The production guide states that Elasticsearch data can be rebuilt with `POST /v1/search/reindex`, so the normal backup focus is PostgreSQL plus media [@production-doc].

## Run Or Inspect Backups

The compose backup service runs `docker/backup.sh` inside the `postgis/postgis:16-3.4` image so `pg_dump` and `psql` versions match the database server [@backup-script]. Each backup writes `db_<timestamp>.sql.gz` from `pg_dump`, writes `media_<timestamp>.tar.gz` when `/media` exists, then prunes database and media archives older than `BACKUP_RETENTION_DAYS` [@backup-script].

Trigger a one-shot backup before a deploy:

```bash
docker compose run --rm backup once
```

The production guide documents `BACKUP_ROOT` as the host destination, defaulting to `/srv/katalon/backups`, and documents `BACKUP_AT`, `BACKUP_INTERVAL_SECONDS`, `BACKUP_RETENTION_DAYS`, and `BACKUP_ENABLED` as the scheduler controls [@production-doc]. `BACKUP_AT` uses the container timezone unless a timezone is set on the service [@production-doc].

## Restore Database And Media

Restore a database dump into the database container with:

```bash
gunzip -c /srv/katalon/backups/db_20260101_030000.sql.gz \
  | docker compose exec -T db psql -U katalon katalon
```

Restore media by extracting the media archive into the media root:

```bash
tar xzf /srv/katalon/backups/media_20260101_030000.tar.gz -C "$MEDIA_ROOT"
```

After a database restore, rebuild search indexes with the reindex endpoint because Elasticsearch can be regenerated from restored records [@production-doc].

When restoring a custom-format dump with `pg_restore`, read stderr before deciding the restore failed. `pg_restore` continues after errors by default and reports the count at the end unless `--exit-on-error` is used [@pg-restore-doc]. With `--clean`, it also tries to drop database objects before recreating them, so a cleanup error can coexist with later import work [@pg-restore-doc]. Treat that as an inconclusive restore, not a success signal: check table counts, compare them with the source instance, sign in, and inspect known records before allowing normal writes again. Restarting the Compose stack does not change whether the database import was complete, and `DROP ... CASCADE` is not a safe way to silence a cleanup message [@agent-rules].

## Run A Restore Drill

The documented restore drill uses a fresh directory and a different `POSTGRES_DB`, starts only `db`, imports the newest dump, checks row counts, extracts media into a test directory, compares file counts, starts the full stack, checks health, and samples the Admin UI [@production-doc]. The same section records a completed drill on 2026-07-13 and recommends repeating the drill at least twice a year [@production-doc].

A second, automated drill (`backend/tests/integration/test_backup_restore_drill.py`, katalon issue #382) proves the pg_dump/psql mechanics on disposable containers rather than the real server: it dumps a freshly-seeded test database, restores it into an unrelated container, and asserts records and their relations survive [@backup-drill-test]. It runs quarterly via `.github/workflows/backup-drill.yml` (schedule-only, never on push) and is a mechanical check, not a substitute for the documented drill above against real backup content [@backup-drill-workflow].

Use [Docker Compose Surfaces](../../reference/operations/docker-compose-surfaces) when the restore environment differs from production mounts or compose files. If the issue began as a database incident, use [DB Problem Escalation](db-problem-escalation) before touching volumes.

For a host move, [Server Migration](../../../docs/06_serverumzug.md) adds the cutover sequence: stop writes, run a final backup, transfer the matching database and media archives plus instance configuration, restore on the target, then rebuild the search index [@migration-doc].

## Avoid Destructive Recovery

Never delete, recreate, or remove database volumes, and never run `docker compose down -v`, without explicit confirmation from Karl [@agent-rules]. The project rule is stricter than ordinary local cleanup because volume deletion is irreversible data loss [@agent-rules]. For database problems, inspect logs, understand the root cause, present options, and wait for explicit approval before any destructive action [@agent-rules].
