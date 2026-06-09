#!/usr/bin/env bash
# Logical backup of the spotify_etl database — pg_dump (inside the postgres
# container, where the binary lives) → gzip on the host → retention prune.
#
# Usage:   tools/db_backup.sh            # → backups/spotify_etl_<UTC>.sql.gz
# Env:     BACKUP_DIR (default ./backups), RETENTION_DAYS (14), PG_CONT (auto),
#          DB_NAME (spotify_etl), DB_USER (postgres).
#
# Designed for a daily cron once on the VPS (Phase D wires it to a Storage Box).
# Runs locally now so the restore drill (db_restore_test.sh) can be exercised.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PG_CONT="${PG_CONT:-$(docker ps --format '{{.Names}}' | grep '^postgres_spotify' | head -1)}"
DB="${DB_NAME:-spotify_etl}"
USER="${DB_USER:-postgres}"
OUT_DIR="${BACKUP_DIR:-$ROOT/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

if [ -z "$PG_CONT" ]; then
    echo "❌ Postgres container not running. Run 'make up' first." >&2
    exit 1
fi

mkdir -p "$OUT_DIR"
STAMP="$(date -u +%Y%m%d_%H%M%S)"
OUT="$OUT_DIR/${DB}_${STAMP}.sql.gz"

echo "→ Dumping '$DB' from container '$PG_CONT' ..."
# --no-owner/--no-privileges keep the dump portable across hosts/roles.
docker exec "$PG_CONT" pg_dump -U "$USER" -d "$DB" --no-owner --no-privileges \
    | gzip > "$OUT"

if [ ! -s "$OUT" ]; then
    echo "❌ Backup is empty — pg_dump likely failed." >&2
    rm -f "$OUT"
    exit 1
fi
echo "✅ Backup written: $OUT ($(du -h "$OUT" | cut -f1))"

# Retention — prune dumps older than RETENTION_DAYS.
find "$OUT_DIR" -name "${DB}_*.sql.gz" -type f -mtime +"$RETENTION_DAYS" -print -delete \
    | sed 's/^/  pruned: /' || true
echo "✅ Retention applied (> ${RETENTION_DAYS} days)."
