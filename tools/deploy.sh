#!/usr/bin/env bash
# Deploy origin/main onto THIS prod server — the one correct way.
#
# Never deploy code with a bare `git pull`: the api/dashboard images COPY src/ at
# BUILD time, so a pull without `--build` leaves the containers running stale code.
# That exact gap 500'd /youtube/videos on 2026-06-14 (checkout had the fix, the
# container did not). This script always pulls AND rebuilds AND health-checks.
#
# Usage (on the prod server):  tools/deploy.sh [service ...]    # default: api dashboard
# Wrapper from a dev machine:  make deploy PROD_SSH=user@host SERVICE="api"
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
SERVICES="${*:-api dashboard}"

echo "▶ git pull --ff-only origin main"
git fetch -q origin main
before="$(git rev-parse --short HEAD)"
git pull --ff-only origin main          # fails loudly on a dirty tree — surfaces drift
after="$(git rev-parse --short HEAD)"
echo "  $before → $after"

# Re-exec if THIS script changed in the pull. Measured on 2026-08-23: the env-parity
# gate was added, pushed, and the very deploy that pulled it did NOT run it — bash reads
# a script incrementally, so the running process kept executing the bytes it had already
# read while the file underneath had been replaced. The deploy reported success and the
# new gate never fired. `exec` restarts from the top with the new content; the guard
# variable stops it from looping.
if [ -z "${DEPLOY_REEXECED:-}" ] && [ "$before" != "$after" ]; then
    echo "▶ deploy.sh may have changed in this pull — re-exec with the new version"
    DEPLOY_REEXECED=1 exec bash "$0" "$@"
fi

echo "▶ rebuild + restart: $SERVICES"
docker compose up -d --build $SERVICES

# Env parity, AFTER the containers are up and BEFORE we declare success. This is the
# 2026-06-19 Benken failure taken at the door: the dashboard container had no
# central-app variable at all, every connection test failed, and nothing said why —
# an absent variable and an empty one are the same thing at the call site.
# `git pull` cannot carry this: the production docker-compose.yml is gitignored.
echo "▶ env parity (presence only — no value is ever printed)"
python3 tools/check_env_parity.py

# The Airflow services run the COLLECTORS, and this script rebuilds api+dashboard only.
# An .env corrected on the box therefore does not reach them. Say so rather than let it
# be discovered a night later.
case " $SERVICES " in
    *" airflow"*) ;;
    *) echo "⚠️  airflow-scheduler / -webserver were NOT recreated by this deploy."
       echo "    If you changed .env or a DAG's credentials, run on the box:"
       echo "    docker compose up -d --force-recreate airflow-scheduler airflow-webserver" ;;
esac

# Health gates: api on 8502/health, dashboard on 8501 Streamlit /_stcore/health.
for s in $SERVICES; do
    case "$s" in
        api)       url="http://127.0.0.1:8502/health" ;;
        dashboard) url="http://127.0.0.1:8501/_stcore/health" ;;
        *)         continue ;;
    esac
    printf "▶ waiting for %s health… " "$s"
    ok=""
    for i in $(seq 1 30); do
        if curl -fsS -o /dev/null --max-time 5 "$url" 2>/dev/null; then ok="${i}s"; break; fi
        sleep 1
    done
    [ -n "$ok" ] || { echo "FAILED ($url did not return 200)"; exit 1; }
    echo "ok ($ok)"
done

echo "✅ deployed $after — $SERVICES healthy"
