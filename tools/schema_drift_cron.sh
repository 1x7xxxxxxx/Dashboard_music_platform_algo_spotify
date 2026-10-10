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
# Email via Brevo SMTP (.env creds) — the box has no MTA, so this is how an alert
# actually reaches the inbox. Best-effort: failure is logged, never fatal.
# notify SUBJECT BODY
notify() {
    NOTIFY="$(printf '%s\n' "$2" | python3 "$ROOT/tools/notify_schema_drift.py" \
        --subject "$1" 2>&1)" || true
    log "notify: $NOTIFY"
    echo "notify: $NOTIFY"
}

# R495 — the CHECK failed: no verdict on prod's schema. Said as such, never as drift,
# and never silently (a dump error used to vanish into 2>/dev/null and abort set -e).
broken() {
    local alert="⊘ SCHEMA DRIFT CHECK BROKEN on $(hostname) — $1. No verdict on prod's schema (this is NOT a drift)."
    log "$alert"
    echo "$alert"
    notify "⊘ streaMLytics schema-drift check broken on $(hostname)" "$alert"
    exit 2
}

docker exec "$CANON" psql -U "$USER" -d "$DB" -tAc "$DUMP_SQL" > "/tmp/${CANON}_canon.tsv" \
    || broken "canonical dump failed (docker exec $CANON psql)"

# 2. Live prod schema (local container).
docker exec "$PG_CONT" psql -U "$USER" -d "$DB" -tAc "$DUMP_SQL" > "/tmp/${CANON}_prod.tsv" \
    || broken "prod dump failed (docker exec $PG_CONT psql)"

# 3. Diff (reuse the dev tool): 0 = clean, 1 + « ⚠ schema drift found » = drift,
#    anything else = the check itself fell over. Full result → log; on drift, a short
#    alert → stdout so a MAILTO crontab mails (clean runs stay silent).
# ⚠️ `OUT="$(…)"; RC=$?` under `set -e` EXITS on the failing substitution before RC is
#    read: until R495 a real drift ended the script here, with no alert and no mail.
RC=0
OUT="$(python3 "$ROOT/tools/dev/schema_drift_check.py" "/tmp/${CANON}_prod.tsv" "/tmp/${CANON}_canon.tsv" 2>&1)" || RC=$?
log "$OUT"
if [ "$RC" -eq 0 ]; then
    exit 0
fi
if ! grep -q '^⚠ schema drift found' <<< "$OUT"; then
    broken "schema_drift_check.py exit $RC without a drift verdict: $(tail -1 <<< "$OUT")"
fi
ALERT="⚠ SCHEMA DRIFT DETECTED on $(hostname) — prod has diverged from init_db.sql + migrations."
echo "$ALERT"
echo "$OUT" | grep -E '^##|absent|^  ' | head -25 || true
echo "Reconcile via a MIGRATION (never a manual ALTER on prod). Full log: $LOG"
notify "⚠ streaMLytics schema drift on $(hostname)" "$(printf '%s\n\n%s' "$ALERT" "$OUT")"
exit 1
