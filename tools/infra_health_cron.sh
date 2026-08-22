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
PG_CONTAINER="${PG_CONTAINER:-postgres_spotify_airflow}"

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

# 4. The watchdog needs a watchdog.
#
# `alert_monitor` is what tells you about everything else — failing DAGs, stale
# sources, broken central apps, a mute canary. It is absent from its own
# MONITORED_DAGS, and it cannot be otherwise: a DAG that does not run cannot report
# that it did not run. Paused, erroring at import, or scheduler down ⇒ total
# silence, which is exactly what a healthy night looks like.
#
# This script is the right place by its own docstring: the host layer, outside
# Airflow. It reads Airflow's metadata DB directly for a recent run in a terminal
# state, so "the scheduler never picked it up" and "it ran and failed" are both
# caught — and they are different problems.
ALERT_DAG="${ALERT_DAG:-alert_monitor}"
ALERT_MAX_AGE_H="${ALERT_MAX_AGE_H:-26}"
row="$(docker exec "$PG_CONTAINER" psql -U postgres -d "${AIRFLOW_DB:-airflow_db}" -tAc \
    "SELECT state, EXTRACT(EPOCH FROM (now() - COALESCE(end_date, start_date)))/3600
       FROM dag_run WHERE dag_id = '$ALERT_DAG'
      ORDER BY COALESCE(end_date, start_date) DESC NULLS LAST LIMIT 1;" 2>/dev/null)"
if [ -z "$row" ]; then
    PROBLEMS+=("WATCHDOG: no run of '$ALERT_DAG' found at all — nothing is watching the pipeline")
else
    state="${row%%|*}"; age="${row##*|}"
    age_h="${age%%.*}"
    if [ -z "$age_h" ]; then age_h=9999; fi
    if [ "$age_h" -ge "$ALERT_MAX_AGE_H" ]; then
        PROBLEMS+=("WATCHDOG: last '$ALERT_DAG' run was ${age_h}h ago (>=${ALERT_MAX_AGE_H}h) — it is not running, so its silence means nothing")
    elif [ "$state" != "success" ]; then
        PROBLEMS+=("WATCHDOG: last '$ALERT_DAG' run ended '$state' ${age_h}h ago — the alert path itself is broken")
    else
        log "watchdog OK: $ALERT_DAG succeeded ${age_h}h ago"
    fi
fi

# 5. The watchdog ran — but did anyone RECEIVE it?
#
# Check 4 above proves `alert_monitor` executed and succeeded. It cannot prove the
# email left the building, and for three consecutive nights (16, 17, 18 August 2026)
# it did not: `send_alert` returned False on a container with no SMTP env, the return
# value was discarded, and the task logged "Consolidated alert sent" and went green.
# Every layer reported health while nothing was delivered.
#
# `monitoring_run` (migration 073) is written by the task itself, before the attempt
# and updated after. This script is the right reader for it: it mails through Brevo
# (tools/notify_schema_drift.py), a DIFFERENT path from the app's SMTP — so it
# survives precisely the outage that silences the alert it is watching.
ALERT_DELIVERY_MAX_AGE_H="${ALERT_DELIVERY_MAX_AGE_H:-48}"
delivery="$(docker exec "$PG_CONTAINER" psql -U postgres -d "${APP_DB:-spotify_etl}" -tAc \
    "SELECT delivered, delivery_expected,
            EXTRACT(EPOCH FROM (now() - run_at))/3600, COALESCE(delivery_error, '')
       FROM monitoring_run ORDER BY run_at DESC LIMIT 1;" 2>/dev/null)"
if [ -z "$delivery" ]; then
    # Before migration 073 this table does not exist; do not invent a problem on an
    # older deployment. Say it is unreadable rather than claiming health.
    log "delivery ledger unreadable (monitoring_run absent?) — not asserting on it"
else
    IFS='|' read -r d_ok d_expected d_age d_err <<< "$delivery"
    d_age_h="${d_age%%.*}"; [ -z "$d_age_h" ] && d_age_h=9999
    if [ "$d_age_h" -ge "$ALERT_DELIVERY_MAX_AGE_H" ]; then
        PROBLEMS+=("DELIVERY: last alert-delivery record is ${d_age_h}h old (>=${ALERT_DELIVERY_MAX_AGE_H}h) — the monitor has not tried to reach you")
    elif [ "$d_expected" = "t" ] && [ "$d_ok" != "t" ]; then
        PROBLEMS+=("DELIVERY: findings existed and the alert was NOT delivered — ${d_err}")
    else
        log "delivery OK: last alert-delivery record ${d_age_h}h ago (delivered=$d_ok, expected=$d_expected)"
    fi
fi

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
