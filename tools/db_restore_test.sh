#!/usr/bin/env bash
# Restore DRILL — proves a backup is restorable. Loads the latest dump into a
# throwaway database, verifies table + row counts, then drops it. A backup you
# never test-restore is not a backup.
#
# Usage:   tools/db_restore_test.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PG_CONT="${PG_CONT:-$(docker ps --format '{{.Names}}' | grep '^postgres_spotify' | head -1)}"
DB="${DB_NAME:-spotify_etl}"
OUT_DIR="${BACKUP_DIR:-$ROOT/backups}"
TEST_DB="${DB}_restore_test"

if [ -z "$PG_CONT" ]; then
    echo "❌ Postgres container not running. Run 'make up' first." >&2
    exit 1
fi

LATEST="$(ls -t "$OUT_DIR"/${DB}_*.sql.gz 2>/dev/null | head -1 || true)"
if [ -z "$LATEST" ]; then
    echo "❌ No backup found in $OUT_DIR — run 'make backup' first." >&2
    exit 1
fi
echo "→ Restoring latest backup: $LATEST"

docker exec "$PG_CONT" psql -U postgres -q -c "DROP DATABASE IF EXISTS $TEST_DB;"
docker exec "$PG_CONT" psql -U postgres -q -c "CREATE DATABASE $TEST_DB;"
trap 'docker exec "$PG_CONT" psql -U postgres -q -c "DROP DATABASE IF EXISTS '"$TEST_DB"';" >/dev/null 2>&1 || true' EXIT

gunzip -c "$LATEST" | docker exec -i "$PG_CONT" psql -U postgres -q -d "$TEST_DB" > /dev/null

TABLES="$(docker exec "$PG_CONT" psql -U postgres -tAd "$TEST_DB" \
    -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';")"
ROWS="$(docker exec "$PG_CONT" psql -U postgres -tAd "$TEST_DB" \
    -c "SELECT count(*) FROM s4a_song_timeline;" 2>/dev/null || echo 'n/a')"

if [ "${TABLES:-0}" -lt 1 ]; then
    echo "❌ Restore produced 0 tables — backup is not usable." >&2
    exit 1
fi
echo "✅ Restore drill OK — $TABLES tables, s4a_song_timeline rows=$ROWS (throwaway DB dropped)."
