#!/bin/sh
# Katalon backup loop: daily pg_dump (gzip) + media tar, with retention.
# Runs inside a postgres:16-alpine container (pg_dump 16 + busybox tar/gzip/find).
# Restore is documented in docs/04_produktion.md.
set -eu

BACKUP_DIR=/backups
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
INTERVAL="${BACKUP_INTERVAL_SECONDS:-86400}"

run_backup() {
  ts="$(date +%Y%m%d_%H%M%S)"

  echo "[$(date -Iseconds)] pg_dump -> db_${ts}.sql.gz"
  # PGPASSWORD is read from the environment by pg_dump.
  pg_dump -h "${POSTGRES_HOST:-db}" -U "${POSTGRES_USER:-katalon}" "${POSTGRES_DB:-katalon}" \
    | gzip > "${BACKUP_DIR}/db_${ts}.sql.gz.tmp"
  mv "${BACKUP_DIR}/db_${ts}.sql.gz.tmp" "${BACKUP_DIR}/db_${ts}.sql.gz"

  if [ -d /media ]; then
    echo "[$(date -Iseconds)] tar media -> media_${ts}.tar.gz"
    tar czf "${BACKUP_DIR}/media_${ts}.tar.gz.tmp" -C /media . \
      && mv "${BACKUP_DIR}/media_${ts}.tar.gz.tmp" "${BACKUP_DIR}/media_${ts}.tar.gz"
  fi

  echo "[$(date -Iseconds)] prune older than ${RETENTION_DAYS} days"
  find "${BACKUP_DIR}" -name 'db_*.sql.gz' -mtime "+${RETENTION_DAYS}" -delete
  find "${BACKUP_DIR}" -name 'media_*.tar.gz' -mtime "+${RETENTION_DAYS}" -delete
  echo "[$(date -Iseconds)] done"
}

# One-shot mode for a manual run / restore drill: `backup.sh once`.
if [ "${1:-}" = "once" ]; then
  run_backup
  exit 0
fi

while true; do
  run_backup || echo "[$(date -Iseconds)] backup FAILED (will retry next interval)"
  sleep "${INTERVAL}"
done
