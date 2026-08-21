#!/usr/bin/env bash
# Apply every migrations/*.sql against the live database — the one correct way.
#
# Why a script and not just a Makefile recipe: `make` is NOT installed on the
# production server (measured 2026-08-21 — `make migrate` there exits 127). The
# deploy path already solved this by putting the logic in `tools/deploy.sh` and
# having `make deploy` do `ssh … bash tools/deploy.sh`. This is the same shape,
# so a procedure that says "run this on prod" is finally true.
#
# Two properties this file exists to preserve:
#
#  1. It keeps going after an error. The migration set is idempotent as a
#     COMPLETE run, not file by file: 024 drops the s4a_song_playlist_adds
#     primary key and fails to recreate it (the three-column form became
#     impossible once 044 made the key window-aware), and 044 then restores the
#     right one. Stopping at the first error would leave that table with no
#     primary key. `ON_ERROR_STOP` is therefore deliberately NOT set.
#
#  2. It never stays silent about those errors. `psql` exits 0 even when
#     statements failed, and the old recipe discarded its output — so the target
#     printed success either way. Every file that produced an ERROR or FATAL is
#     named at the end, with the command that proves the schema actually landed.
#
# Usage (anywhere the repo and Docker are):  bash tools/migrate.sh
# Wrapper from a dev machine to prod:        make migrate-prod PROD_SSH=user@host
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PG_CONT="${PG_CONT:-$(docker ps --format '{{.Names}}' | grep '^postgres_spotify' | head -1)}"
if [ -z "$PG_CONT" ]; then
    echo "❌ No running Postgres container matching 'postgres_spotify*'." >&2
    echo "   Run: docker compose up -d postgres   (locally: make up)" >&2
    exit 1
fi

DB="${PGDATABASE:-spotify_etl}"
USER_="${PGUSER:-postgres}"

shopt -s nullglob
FILES=(migrations/*.sql)
if [ ${#FILES[@]} -eq 0 ]; then
    echo "❌ No migrations/*.sql found under $ROOT." >&2
    exit 1
fi

echo "▶ ${#FILES[@]} migration(s) → $PG_CONT/$DB"

# Re-running a migration whose object is already there is the NORMAL case: this
# script is meant to be idempotent as a whole, and most files predate
# `IF NOT EXISTS`. Those errors carry no information. Reporting them next to a
# real one taught the reader to skip the whole block — measured on the first
# production run of this script, which named five files of which four were noise.
# So: classify, do not filter. Noise is counted, the rest is named.
IDEMPOTENT_RE='already exists|does not exist'

noisy=()
real=()
declare -A real_msg
for f in "${FILES[@]}"; do
    echo ">> $f"
    out="$(docker exec -i "$PG_CONT" psql -U "$USER_" -d "$DB" < "$f" 2>&1)"
    printf '%s\n' "$out"

    errs="$(printf '%s' "$out" | grep -iE '^(ERROR|FATAL)')"
    [ -z "$errs" ] && continue

    unexpected="$(printf '%s' "$errs" | grep -viE "$IDEMPOTENT_RE")"
    if [ -n "$unexpected" ]; then
        real+=("$f")
        real_msg["$f"]="$(printf '%s' "$unexpected" | head -2)"
    else
        noisy+=("$f")
    fi
done

echo ""
[ ${#noisy[@]} -gt 0 ] && echo "ℹ️  ${#noisy[@]} file(s) re-applied over existing objects (expected on any re-run)."

if [ ${#real[@]} -eq 0 ]; then
    echo "✅ no unexpected psql error"
    exit 0
fi

echo "⚠️  ${#real[@]} file(s) reported an error that is NOT a re-run artefact:"
for f in "${real[@]}"; do
    echo "     $f"
    printf '%s\n' "${real_msg[$f]}" | sed 's/^/         /'
done
cat <<'MSG'

   A complete run is expected to heal some of these — a later migration can
   supersede an earlier one (024 → 044 is the known pair, and 024's three-column
   key has been impossible since 044 made it window-aware). Confirm that it did.
   Do not assume it:

     make schema-check PROD_SSH=<user@host>

   Exit code stays 0: stopping here is what would actually leave the schema
   half-applied. The list above is the signal.
MSG
exit 0
