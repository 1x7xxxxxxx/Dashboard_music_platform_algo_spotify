#!/usr/bin/env bash
# Which migrations exist in the repo but have NOT been applied on the target?
#
# Impossible to ask before 2026-08-21: nothing recorded what had run, so the only
# strategy was "reapply everything and hope". The `schema_migrations` ledger makes
# the question a one-line diff, and it closes `migration-ahead-of-its-code` from the
# side that hurt: a migration applied to prod BEFORE its code was deployed broke
# YouTube collection within minutes. The reverse — code deployed before its
# migration — is just as damaging and had no detector either.
#
# Also checks that the operational scripts are reachable inside the containers: the
# production compose is GITIGNORED, so the ./tools mount added on 2026-08-21 does not
# travel with `git pull`. If that file is ever regenerated from the example, the mount
# is silently lost and every runbook step that runs a tool stops working.
#
# Usage: bash tools/dev/check_prod_ledger.sh <user@host> [container]
set -uo pipefail

SSH_TARGET="${1:?usage: check_prod_ledger.sh <user@host> [pg_container]}"
PG="${2:-postgres_spotify_airflow}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

applied="$(ssh -o ConnectTimeout=10 "$SSH_TARGET" \
    "docker exec $PG psql -U postgres -d spotify_etl -tAc 'SELECT filename FROM schema_migrations ORDER BY 1' 2>/dev/null" \
    | tr -d '\r' | sed '/^$/d' | sort)"

if [ -z "$applied" ]; then
    echo "⚠ no schema_migrations table on the target — run tools/migrate.sh there once."
    exit 1
fi

repo="$(cd "$ROOT" && ls -1 migrations/*.sql | xargs -n1 basename | sort)"
pending="$(comm -23 <(printf '%s\n' "$repo") <(printf '%s\n' "$applied"))"
extra="$(comm -13 <(printf '%s\n' "$repo") <(printf '%s\n' "$applied"))"

rc=0
if [ -n "$pending" ]; then
    echo "⚠ MIGRATION DRIFT — in the repo, NOT applied on the target:"
    printf '     %s\n' $pending
    echo "   Run on the target: bash tools/migrate.sh"
    rc=1
fi
if [ -n "$extra" ]; then
    echo "⚠ applied on the target but ABSENT from the repo (deleted or renamed?):"
    printf '     %s\n' $extra
    rc=1
fi
[ $rc -eq 0 ] && echo "  ✅ migrations: $(printf '%s\n' "$repo" | wc -l) in the repo, all recorded as applied"

# The mount that the gitignored compose does not carry.
if ssh -o ConnectTimeout=10 "$SSH_TARGET" \
     'docker exec airflow_scheduler test -f /opt/airflow/tools/create_canary.py' 2>/dev/null; then
    echo "  ✅ tools/ reachable inside airflow_scheduler"
else
    echo "⚠ tools/ is NOT mounted in airflow_scheduler — every runbook step that runs a"
    echo "   tool will fail with \"can't open file\". The production docker-compose.yml is"
    echo "   gitignored, so this does NOT arrive by git pull. Add under each airflow service:"
    echo "       - ./tools:/opt/airflow/tools:ro"
    rc=1
fi
exit $rc
