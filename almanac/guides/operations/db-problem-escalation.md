---
title: "DB Problem Escalation"
summary: "Database incidents in Katalon require log-first diagnosis and explicit human approval before any volume-destructive action."
topics: [operations, database, safety]
sources:
  - id: agents
    type: file
    path: AGENTS.md
  - id: playbook
    type: file
    path: .agents/knowledge/playbooks/db-problem-eskalation.md
  - id: compose
    type: file
    path: docker-compose.yml
---

Use this guide when PostgreSQL fails to start, credentials do not match, migrations appear broken, or a container error points at database state. Katalon's operational rule is strict: diagnose from logs first, explain options to Karl, and do not delete or recreate database volumes without explicit approval [@agents] [@playbook]. The reason is concrete in the Compose stack: PostgreSQL stores persistent state in the named `db_data` volume, while the backup service reads that database and writes backups elsewhere [@compose].

## First Response

Start by reading logs from the service that reports the problem and from `db`. The project instruction says database errors must be investigated from container logs instead of assumptions [@agents]. For Compose incidents, the smallest useful first pass is usually:

```bash
docker compose logs db
docker compose logs api
docker compose ps
```

Keep the first pass read-only. Do not run `docker compose down -v`, remove `db_data`, recreate the database volume, or replace the volume as a quick fix. The repository playbook names password conflicts, schema problems, and Postgres container failures as triggers for this escalation path [@playbook].

## Determine Blast Radius

Separate startup, credential, migration, and data problems before proposing a fix. `docker-compose.yml` defines `db` with the PostGIS image, the `POSTGRES_*` environment variables, a `pg_isready` healthcheck, and the named `db_data` volume at `/var/lib/postgresql/data` [@compose]. The API waits for a healthy database and receives `DATABASE_URL`, so an API startup failure can be a downstream symptom of a database health or credential problem [@compose].

Also check whether the backup service is relevant. The Compose file includes a `backup` service using the PostGIS image, `PGPASSWORD`, `/backup.sh`, the media directory as read-only input, and a backup output mount [@compose]. If the incident includes suspected data loss or a need to roll back, inspect backup availability before suggesting any repair that changes persistent database state.

## Escalate Before Destructive Repair

When the likely fix would delete, recreate, overwrite, or reinitialize database state, stop and present Karl with the evidence, the risk, and the options. The standing instruction is absolute: never delete database volumes, recreate them, or run `docker compose down -v` without Karl's explicit confirmation because data loss is irreversible [@agents]. The local playbook repeats the same three-step escalation: read logs, understand root cause, inform Karl with options, then act only after explicit approval [@playbook].

Good escalation messages name the exact command being considered. "Reset the database" is too vague. "`docker compose down -v` would remove `db_data`; I will not run it without confirmation" is the level of specificity this guide requires.

## Verification

After a non-destructive fix, verify the actual service boundary that failed. For database availability, `docker compose ps` should show the `db` healthcheck as healthy, and `docker compose logs db` should no longer show the root error. For an API symptom, confirm the API healthcheck recovers because `api` depends on a healthy database [@compose].

If the incident required a restore, verify that the restored database is the intended source of truth before allowing normal writes again. Katalon has operational guidance for backup and restore elsewhere in the wiki, but this page's rule is narrower: do not trade a database incident for silent data loss.
