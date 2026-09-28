#!/usr/bin/env bash
# backup_db.sh — Daily PostgreSQL backup via pg_dump inside Docker container.
#
# Usage (manual):
#   bash scripts/backup_db.sh
#
# Usage (cron — add to crontab on the Hetzner VPS):
#   0 3 * * * /opt/music-dashboard/scripts/backup_db.sh >> /var/log/backup_db.log 2>&1
#
# Retention: keeps last 7 daily backups, deletes older ones automatically.
# Storage:   /opt/backups/postgres/ (change BACKUP_DIR below if needed)
#
# Requirements on VPS:
#   - Docker running with a container named postgres_spotify_airflow (or set CONTAINER below)
#   - /opt/backups/postgres/ directory writable by the cron user

set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────────
CONTAINER="${POSTGRES_CONTAINER:-postgres_spotify_airflow}"
DB_NAME="${POSTGRES_DB:-spotify_etl}"
DB_USER="${POSTGRES_USER:-postgres}"
BACKUP_DIR="${BACKUP_DIR:-/opt/backups/postgres}"
RETENTION_DAYS=7
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILENAME="${DB_NAME}_${TIMESTAMP}.sql.gz"

# ── Run ──────────────────────────────────────────────────────────────────────
mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting backup → ${BACKUP_DIR}/${FILENAME}"

docker exec "$CONTAINER" \
    pg_dump -U "$DB_USER" "$DB_NAME" \
  | gzip > "${BACKUP_DIR}/${FILENAME}"

SIZE=$(du -sh "${BACKUP_DIR}/${FILENAME}" | cut -f1)
echo "[$(date)] Backup complete — ${FILENAME} (${SIZE})"

# ── Rotate: delete backups older than RETENTION_DAYS ─────────────────────────
find "$BACKUP_DIR" -name "${DB_NAME}_*.sql.gz" -mtime +"$RETENTION_DAYS" -delete
echo "[$(date)] Retention: removed backups older than ${RETENTION_DAYS} days"

# ── Verify: list current backups ──────────────────────────────────────────────
echo "[$(date)] Current backups:"
ls -lh "$BACKUP_DIR"/${DB_NAME}_*.sql.gz 2>/dev/null || echo "  (none)"
