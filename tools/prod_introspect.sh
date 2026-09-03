#!/usr/bin/env bash
#
# prod_introspect.sh — READ-ONLY one-command prod diagnostic.
#
# Codified version of the manual probes run during the "Benken incident"
# (2026-06-15): a tenant configured correctly yet showing 0 rows because the
# central-app env vars were wired into some containers but not others, DAGs
# failing daily unnoticed, and collectors reporting "success" with 0 rows per
# tenant. This script SSHes to prod and prints three surfaces in one shot:
#
#   (a) per-container presence (SET / MISSING — never the value) of the central
#       credential env vars + Fernet key + Airflow admin creds, for the two
#       containers that read them most surprisingly (dashboard runs the
#       connection tests; scheduler runs the collectors).
#   (b) recent DAG run states for the collector DAGs (last 3 days) from airflow_db.
#   (c) per-tenant row counts in the main collector tables, from spotify_etl.
#
# It mutates nothing: only `printenv`, `psql -tA -c "SELECT ..."`, and
# `docker exec` reads. Host overridable via PROD_SSH.
#
# Usage:
#   ./tools/prod_introspect.sh
#   PROD_SSH=root@10.0.0.9 ./tools/prod_introspect.sh

set -euo pipefail

PROD_SSH="${PROD_SSH:-root@167.233.92.1}"
SSH=(ssh -o BatchMode=yes -o ConnectTimeout=12 "$PROD_SSH")

# Containers that authenticate to platforms (the Benken surprise: the dashboard
# needs the central env too, because it runs the per-artist connection tests).
CONTAINERS=(streamlytics_dashboard airflow_scheduler)

# Central credential model env vars (ADR-006) + Fernet + Airflow admin.
ENV_VARS=(
  FERNET_KEY
  SPOTIFY_CLIENT_ID SPOTIFY_CLIENT_SECRET
  YOUTUBE_API_KEY
  SOUNDCLOUD_CLIENT_ID SOUNDCLOUD_CLIENT_SECRET
  META_ACCESS_TOKEN META_APP_ID META_APP_SECRET
  AIRFLOW_ADMIN_USERNAME AIRFLOW_ADMIN_PASSWORD
)

# Collector DAGs whose daily runs must be observed (were failing unnoticed).
COLLECTOR_DAGS=(
  youtube_daily soundcloud_daily instagram_daily
  spotify_api_daily meta_ads_api_daily
)

run_remote() {
  # Run a command on prod with a hard wall-clock cap.
  timeout 90 "${SSH[@]}" "$@"
}

section() {
  printf '\n========================================================================\n'
  printf '  %s\n' "$1"
  printf '========================================================================\n'
}

# ---------------------------------------------------------------------------
# (a) Per-container env presence — SET / MISSING, never the value.
# ---------------------------------------------------------------------------
audit_env() {
  section "(a) Central-app env presence per container (SET / MISSING)"
  for c in "${CONTAINERS[@]}"; do
    printf '\n--- container: %s ---\n' "$c"
    for v in "${ENV_VARS[@]}"; do
      status=$(run_remote \
        "docker exec \"$c\" printenv \"$v\" >/dev/null 2>&1 && echo SET || echo MISSING" \
        2>/dev/null || echo "ERR")
      printf '  %-26s %s\n' "$v" "$status"
    done
  done
}

# ---------------------------------------------------------------------------
# (b) Recent DAG run states from airflow_db (last 3 days).
# ---------------------------------------------------------------------------
audit_dag_runs() {
  section "(b) Collector DAG runs — last 3 days (dag_id | state | run | count)"
  local in_list
  in_list=$(printf "'%s'," "${COLLECTOR_DAGS[@]}")
  in_list="${in_list%,}"
  local sql="SELECT dag_id, state, count(*), max(execution_date)
             FROM dag_run
             WHERE dag_id IN (${in_list})
               AND execution_date > now() - interval '3 days'
             GROUP BY dag_id, state
             ORDER BY dag_id, state;"
  run_remote \
    "docker exec postgres_spotify_airflow psql -U postgres -d airflow_db -tA -c \"${sql}\"" \
    2>/dev/null || echo "  (airflow_db query failed)"
}

# ---------------------------------------------------------------------------
# (c) Per-tenant row counts in the main collector tables (spotify_etl).
# ---------------------------------------------------------------------------
audit_tenant_rows() {
  section "(c) Per-tenant row counts in collector tables (spotify_etl)"
  local sql="SELECT a.artist_id, a.name,
               (SELECT count(*) FROM soundcloud_tracks_daily t
                  WHERE t.artist_id = a.artist_id)            AS soundcloud,
               (SELECT count(*) FROM youtube_videos t
                  WHERE t.artist_id = a.artist_id)            AS youtube,
               (SELECT count(*) FROM track_popularity_history t
                  WHERE t.artist_id = a.artist_id)            AS spotify,
               (SELECT count(*) FROM meta_insights_performance_day t
                  WHERE t.artist_id = a.artist_id)            AS meta
             FROM saas_artists a
             WHERE a.is_active = true
             ORDER BY a.artist_id;"
  run_remote \
    "docker exec postgres_spotify_airflow psql -U postgres -d spotify_etl -tA -c \"${sql}\"" \
    2>/dev/null || echo "  (spotify_etl query failed)"
}

main() {
  printf 'prod_introspect.sh — READ-ONLY diagnostic against %s\n' "$PROD_SSH"
  audit_env
  audit_dag_runs
  audit_tenant_rows
  printf '\nDone.\n'
}

main "$@"
