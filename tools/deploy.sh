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

echo "▶ rebuild + restart: $SERVICES"
docker compose up -d --build $SERVICES

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
