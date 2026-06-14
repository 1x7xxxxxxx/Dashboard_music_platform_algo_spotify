#!/usr/bin/env bash
# Daily infra health check (runs ON the prod server) — the host-observable layer.
#
# Verifies what neither the external GitHub Actions probe nor the on-box Airflow DAGs
# can (a DAG can't watch its own scheduler; backup files + disk live on the host):
#   1. the nightly pg_dump actually produced a FRESH, non-empty backup
#      (would have caught the 2026-06-14 incident: db_backup.sh lost its exec bit →
#       no backup since 2026-06-12, silently)
#   2. disk headroom on /
#   3. all core containers are Up
#
# Alerts via Brevo (tools/notify_schema_drift.py — generic SMTP sender, body on stdin),
# since the box has no MTA. Exit non-zero + email on any failure; a clean run prints
# nothing to stdout (so a MAILTO crontab only mails on problems) and exits 0.
#
# Cron (sibling of the 4h schema-drift check):
#   0 5 * * * /opt/streamlytics/tools/infra_health_cron.sh >> /var/log/streamlytics-infra-health.log 2>&1
#
# Env knobs: BACKUP_DIR (default ./backups), BACKUP_MAX_AGE_H (25), DISK_MAX_PCT (85),
#            DB_NAME (spotify_etl), CONTAINERS (space-separated), LOG.
set -uo pipefail   # NOT -e: run every check, then aggregate failures.

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
DB="${DB_NAME:-spotify_etl}"
BACKUP_MAX_AGE_H="${BACKUP_MAX_AGE_H:-25}"
DISK_MAX_PCT="${DISK_MAX_PCT:-85}"
CONTAINERS="${CONTAINERS:-postgres_spotify_airflow airflow_scheduler streamlytics_dashboard streamlytics_api}"
LOG="${LOG:-/var/log/streamlytics-infra-health.log}"

log() { echo "$@" >> "$LOG" 2>/dev/null || echo "$@" >&2; }
log "── infra health $(date -u +%Y-%m-%dT%H:%M:%SZ) ──"

PROBLEMS=()

# 1. Backup freshness: newest dump younger than BACKUP_MAX_AGE_H AND non-empty.
newest="$(ls -t "$BACKUP_DIR"/"${DB}"_*.sql.gz 2>/dev/null | head -1)"
if [ -z "$newest" ]; then
    PROBLEMS+=("BACKUP: no dump found in $BACKUP_DIR")
else
    age_h=$(( ( $(date +%s) - $(stat -c %Y "$newest") ) / 3600 ))
    size=$(stat -c %s "$newest")
    if [ "$age_h" -ge "$BACKUP_MAX_AGE_H" ]; then
        PROBLEMS+=("BACKUP: newest dump is ${age_h}h old (>=${BACKUP_MAX_AGE_H}h) — $newest")
    elif [ "$size" -lt 1000 ]; then
        PROBLEMS+=("BACKUP: newest dump is ${size}B (looks empty) — $newest")
    else
        log "backup OK: $newest (${age_h}h, ${size}B)"
    fi
fi

# 2. Disk headroom on /.
used="$(df --output=pcent / | tail -1 | tr -dc '0-9')"
if [ "${used:-100}" -ge "$DISK_MAX_PCT" ]; then
    PROBLEMS+=("DISK: / at ${used}% (>=${DISK_MAX_PCT}%)")
else
    log "disk OK: /=${used}%"
fi

# 3. Container liveness.
for c in $CONTAINERS; do
    state="$(docker inspect -f '{{.State.Status}}' "$c" 2>/dev/null || echo missing)"
    if [ "$state" != "running" ]; then
        PROBLEMS+=("CONTAINER: $c is '$state' (expected running)")
    else
        log "container OK: $c running"
    fi
done

# Verdict — clean run stays silent on stdout.
if [ "${#PROBLEMS[@]}" -eq 0 ]; then
    log "ALL OK"
    exit 0
fi

ALERT="⚠ streaMLytics infra health FAILED on $(hostname):"
echo "$ALERT"
for p in "${PROBLEMS[@]}"; do echo "  - $p"; log "PROBLEM: $p"; done

# Email via Brevo (.env creds) — best-effort, never fatal.
NOTIFY="$({ printf '%s\n\n' "$ALERT"; printf '  - %s\n' "${PROBLEMS[@]}"; } \
    | python3 "$ROOT/tools/notify_schema_drift.py" \
        --subject "⚠ streaMLytics infra health on $(hostname)" 2>&1)" || true
log "notify: $NOTIFY"
echo "notify: $NOTIFY"
exit 1
