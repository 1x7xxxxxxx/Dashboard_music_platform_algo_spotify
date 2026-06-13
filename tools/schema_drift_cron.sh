#!/usr/bin/env bash
# Nightly prod ↔ canonical schema-drift check (runs ON the prod server).
#
# Provisions a throwaway Postgres from the version-controlled schema (init_db.sql +
# migrations/*.sql), dumps its information_schema, dumps the live prod DB (local
# `docker exec`), and diffs them with tools/dev/schema_drift_check.py. Exits non-zero
# (+ prints "SCHEMA DRIFT DETECTED") when prod has drifted — so a `MAILTO=` crontab
# mails you automatically. Catches a manual ALTER on prod that bypassed migrations.
#
# Cron (after the 3h backup):
#   MAILTO="you@example.com"
#   0 4 * * * /opt/streamlytics/tools/schema_drift_cron.sh >> /var/log/streamlytics-schema-drift.log 2>&1
#
# Env: PG_CONT (auto prod container), DB_NAME (spotify_etl), DB_USER (postgres),
#      CANON_IMAGE (postgres:17).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PG_CONT="${PG_CONT:-$(docker ps --format '{{.Names}}' | grep '^postgres_spotify' | head -1)}"
DB="${DB_NAME:-spotify_etl}"
USER="${DB_USER:-postgres}"
CANON_IMAGE="${CANON_IMAGE:-postgres:17}"
CANON="_schema_canon_$$"
DUMP_SQL="SELECT table_name||'.'||column_name FROM information_schema.columns WHERE table_schema='public' ORDER BY 1"

echo "── schema-drift check $(date -u +%Y-%m-%dT%H:%M:%SZ) ──"

if [ -z "$PG_CONT" ]; then
    echo "❌ prod Postgres container not found (docker ps | grep postgres_spotify)." >&2
    exit 1
fi

cleanup() { docker rm -f "$CANON" >/dev/null 2>&1 || true; rm -f /tmp/${CANON}_*.tsv; }
trap cleanup EXIT

# 1. Throwaway canonical from init_db.sql + migrations (best-effort, like CI).
docker run -d --name "$CANON" -e POSTGRES_PASSWORD=x -e POSTGRES_DB="$DB" "$CANON_IMAGE" >/dev/null
for _ in $(seq 1 30); do docker exec "$CANON" pg_isready -U "$USER" -d "$DB" >/dev/null 2>&1 && break; sleep 1; done
sleep 2
docker exec -i "$CANON" psql -U "$USER" -d "$DB" -v ON_ERROR_STOP=0 -q < "$ROOT/init_db.sql" >/dev/null 2>&1
for f in $(ls "$ROOT"/migrations/*.sql | sort); do
    docker exec -i "$CANON" psql -U "$USER" -d "$DB" -v ON_ERROR_STOP=0 -q < "$f" >/dev/null 2>&1
done
docker exec "$CANON" psql -U "$USER" -d "$DB" -tAc "$DUMP_SQL" > "/tmp/${CANON}_canon.tsv" 2>/dev/null

# 2. Live prod schema (local container).
docker exec "$PG_CONT" psql -U "$USER" -d "$DB" -tAc "$DUMP_SQL" > "/tmp/${CANON}_prod.tsv" 2>/dev/null

# 3. Diff (reuse the dev tool). Non-zero exit = drift.
if python3 "$ROOT/tools/dev/schema_drift_check.py" "/tmp/${CANON}_prod.tsv" "/tmp/${CANON}_canon.tsv"; then
    exit 0
else
    echo "⚠ SCHEMA DRIFT DETECTED — prod has diverged from init_db.sql + migrations."
    echo "  Reconcile via a migration (never a manual ALTER on prod). See"
    echo "  .claude/dev-docs/schema-drift-2026-06-13.md and run \`make schema-check\` locally."
    exit 1
fi
