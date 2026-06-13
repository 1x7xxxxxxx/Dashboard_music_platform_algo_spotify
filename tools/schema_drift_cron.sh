#!/usr/bin/env bash
# Nightly prod ↔ canonical schema-drift check (runs ON the prod server).
#
# Provisions a throwaway Postgres from the version-controlled schema (init_db.sql +
# migrations/*.sql), dumps its information_schema, dumps the live prod DB (local
# `docker exec`), and diffs them with tools/dev/schema_drift_check.py. Exits non-zero
# (+ prints "SCHEMA DRIFT DETECTED") when prod has drifted. On drift it emails an alert
# via the Brevo SMTP creds in .env (tools/notify_schema_drift.py) — no system MTA needed,
# since the box has none. Catches a manual ALTER on prod that bypassed migrations.
#
# Cron (after the 3h backup); self-notifies, so just redirect to the log:
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
CANON="schema_canon_$$"   # must start alphanumeric (docker name rule)
LOG="${LOG:-/var/log/streamlytics-schema-drift.log}"
DUMP_SQL="SELECT table_name||'.'||column_name FROM information_schema.columns WHERE table_schema='public' ORDER BY 1"

# Full output → log (always); stdout stays empty on success so a MAILTO crontab only
# mails on drift. log() appends to $LOG (falls back to stderr if the path isn't writable).
log() { echo "$@" >> "$LOG" 2>/dev/null || echo "$@" >&2; }
log "── schema-drift check $(date -u +%Y-%m-%dT%H:%M:%SZ) ──"

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

# 3. Diff (reuse the dev tool). Non-zero exit = drift. Full result → log; on drift,
#    a short alert → stdout so a MAILTO crontab mails (clean runs stay silent).
OUT="$(python3 "$ROOT/tools/dev/schema_drift_check.py" "/tmp/${CANON}_prod.tsv" "/tmp/${CANON}_canon.tsv" 2>&1)"; RC=$?
log "$OUT"
if [ "$RC" -eq 0 ]; then
    exit 0
fi
ALERT="⚠ SCHEMA DRIFT DETECTED on $(hostname) — prod has diverged from init_db.sql + migrations."
echo "$ALERT"
echo "$OUT" | grep -E '^##|absent|^  ' | head -25
echo "Reconcile via a MIGRATION (never a manual ALTER on prod). Full log: $LOG"

# Email the alert via Brevo SMTP (.env creds) — the box has no MTA, so this is how
# drift actually reaches the inbox. Best-effort: failure is logged, never fatal.
NOTIFY="$({ printf '%s\n\n' "$ALERT"; echo "$OUT"; } | python3 "$ROOT/tools/notify_schema_drift.py" \
    --subject "⚠ streaMLytics schema drift on $(hostname)" 2>&1)" || true
log "notify: $NOTIFY"
echo "notify: $NOTIFY"
exit 1
