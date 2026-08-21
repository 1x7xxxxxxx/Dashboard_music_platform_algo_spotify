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

failed=()
for f in "${FILES[@]}"; do
    echo ">> $f"
    out="$(docker exec -i "$PG_CONT" psql -U "$USER_" -d "$DB" < "$f" 2>&1)"
    printf '%s\n' "$out"
    if printf '%s' "$out" | grep -qiE '^(ERROR|FATAL)'; then
        failed+=("$f")
    fi
done

echo ""
if [ ${#failed[@]} -eq 0 ]; then
    echo "✅ every migration applied with no psql error"
    exit 0
fi

echo "⚠️  psql reported errors in ${#failed[@]} file(s):"
for f in "${failed[@]}"; do echo "     $f"; done
cat <<'MSG'

   A complete run is expected to heal some of these — a later migration can
   supersede an earlier one (024 → 044 is the known pair). Confirm that it did.
   Do not assume it:

     make schema-check PROD_SSH=<user@host>

   Exit code stays 0: stopping here is what would actually leave the schema
   half-applied. The list above is the signal.
MSG
exit 0
