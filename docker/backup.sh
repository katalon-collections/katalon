#!/bin/sh
# Katalon backup loop: pg_dump (gzip) + media tar, with retention.
# Runs inside the postgis/postgis:16-3.4 image (same as the DB server, so
# pg_dump and psql minor versions match). Restore: see docs/04_produktion.md.
#
# Env:
#   BACKUP_ENABLED           true|false (default true) — false = idle, no backups
#   BACKUP_AT                HH:MM daily clock time (e.g. 03:00). Empty = interval mode.
#   BACKUP_INTERVAL_SECONDS  interval mode: seconds between runs (default 86400)
#   BACKUP_RETENTION_DAYS    delete dumps older than N days (default 14)
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

# Sleep until the next BACKUP_AT clock time (GNU date, present in the debian image).
sleep_until_at() {
  now="$(date +%s)"
  target="$(date -d "today ${BACKUP_AT}" +%s 2>/dev/null)" \
    || { echo "invalid BACKUP_AT=${BACKUP_AT}, expected HH:MM"; exit 1; }
  [ "$target" -le "$now" ] && target="$(date -d "tomorrow ${BACKUP_AT}" +%s)"
  wait=$((target - now))
  echo "[$(date -Iseconds)] next backup at ${BACKUP_AT} (in ${wait}s)"
  sleep "$wait"
}

# One-shot mode for a manual run / restore drill: `backup.sh once`.
if [ "${1:-}" = "once" ]; then
  run_backup
  exit 0
fi

case "${BACKUP_ENABLED:-true}" in
  false|0|no|off)
    echo "[$(date -Iseconds)] BACKUP_ENABLED=${BACKUP_ENABLED} — backups disabled, idling"
    exec sleep infinity
    ;;
esac

if [ -n "${BACKUP_AT:-}" ]; then
  # Clock-scheduled mode: wait until the target time, then back up.
  while true; do
    sleep_until_at
    run_backup || echo "[$(date -Iseconds)] backup FAILED (will retry next schedule)"
  done
else
  # Interval mode: back up now, then every INTERVAL seconds.
  while true; do
    run_backup || echo "[$(date -Iseconds)] backup FAILED (will retry next interval)"
    sleep "${INTERVAL}"
  done
fi
