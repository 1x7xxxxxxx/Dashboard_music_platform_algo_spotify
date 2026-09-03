#!/usr/bin/env bash
# Restore DRILL — proves a backup is restorable. Loads the latest dump into a
# throwaway database, verifies table + row counts, then drops it. A backup you
# never test-restore is not a backup.
#
# Usage:   tools/db_restore_test.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PG_CONT="${PG_CONT:-$(docker ps --format '{{.Names}}' | grep '^postgres_spotify' | head -1)}"
DB="${DB_NAME:-spotify_etl}"
OUT_DIR="${BACKUP_DIR:-$ROOT/backups}"
TEST_DB="${DB}_restore_test"

if [ -z "$PG_CONT" ]; then
    echo "❌ Postgres container not running. Run 'make up' first." >&2
    exit 1
fi

LATEST="$(ls -t "$OUT_DIR"/${DB}_*.sql.gz 2>/dev/null | head -1 || true)"
if [ -z "$LATEST" ]; then
    echo "❌ No backup found in $OUT_DIR — run 'make backup' first." >&2
    exit 1
fi
echo "→ Restoring latest backup: $LATEST"

docker exec "$PG_CONT" psql -U postgres -q -c "DROP DATABASE IF EXISTS $TEST_DB;"
docker exec "$PG_CONT" psql -U postgres -q -c "CREATE DATABASE $TEST_DB;"
trap 'docker exec "$PG_CONT" psql -U postgres -q -c "DROP DATABASE IF EXISTS '"$TEST_DB"';" >/dev/null 2>&1 || true' EXIT

gunzip -c "$LATEST" | docker exec -i "$PG_CONT" psql -U postgres -q -d "$TEST_DB" > /dev/null

# Ce que ce drill doit prouver — et ne prouvait pas jusqu'au 2026-09-04.
#
# La version précédente s'arrêtait à `TABLES >= 1` et AFFICHAIT un compte de lignes
# sans jamais le comparer à quoi que ce soit. Un dump tronqué à la première table, ou
# un `pg_dump` qui n'aurait sorti que le schéma, passait au vert : c'était un contrôle
# de `gunzip` déguisé en contrôle de sauvegarde.
#
# La question est « la base restaurée contient-elle ce que contient la vivante ? ».
# Elle se pose donc en COMPARANT les deux.
count_tables() {  # $1 = database
    docker exec "$PG_CONT" psql -U postgres -tAd "$1" \
        -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';"
}
# Compte EXACT, pas `pg_stat_user_tables.n_live_tup`. Mesuré le 2026-09-04 : la
# première version comparait deux estimations et rendait « 40 015 restaurées contre
# 1 149 vivantes » sur la même base — `n_live_tup` n'est rafraîchi que par ANALYZE et
# l'autovacuum, donc il était périmé côté vivant et frais côté restauré. Un garde bâti
# sur une estimation compare du bruit.
#
# `query_to_xml` exécute un `count(*)` par table depuis SQL : c'est plus lent qu'une
# statistique, et à 49 000 lignes c'est instantané. La justesse prime, ici.
count_rows() {    # $1 = database — somme exacte des lignes, toutes tables de base
    docker exec "$PG_CONT" psql -U postgres -tAd "$1" -c "
        SELECT COALESCE(sum(n), 0) FROM (
          SELECT (xpath('/row/c/text()',
                   query_to_xml(format('SELECT count(*) AS c FROM %I.%I',
                                       table_schema, table_name),
                                false, true, '')))[1]::text::bigint AS n
          FROM information_schema.tables
          WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ) s;"
}

TABLES="$(count_tables "$TEST_DB")"
LIVE_TABLES="$(count_tables "$DB")"
ROWS="$(count_rows "$TEST_DB")"
LIVE_ROWS="$(count_rows "$DB")"

if [ "${TABLES:-0}" -lt 1 ]; then
    echo "❌ Restore produced 0 tables — backup is not usable." >&2
    exit 1
fi

# Le schéma ne doit PAS avoir bougé entre la sauvegarde et maintenant : une migration
# appliquée entre-temps est une information, pas un échec — mais elle doit se voir.
if [ "${TABLES}" -ne "${LIVE_TABLES}" ]; then
    echo "⚠️  Schéma différent : $TABLES tables restaurées contre $LIVE_TABLES vivantes." >&2
    echo "    Une migration a été appliquée depuis la sauvegarde — attendu si tu viens" >&2
    echo "    d'en passer une, suspect sinon." >&2
fi

# Tolérance sur les lignes, calibrée sur la croissance MESURÉE : 2 736 lignes/jour au
# 2026-09-03 pour ~49 000 en base, soit ~5,6 %/jour. 10 % laisse passer près de deux
# jours d'écart entre la sauvegarde et le drill sans crier, et attrape un dump qui
# aurait perdu un ordre de grandeur. Le seuil est ici parce qu'il a été calculé, pas
# parce que 10 est un chiffre rond.
if [ "${LIVE_ROWS:-0}" -gt 0 ]; then
    MIN_ROWS=$(( LIVE_ROWS * 90 / 100 ))
    if [ "${ROWS:-0}" -lt "$MIN_ROWS" ]; then
        echo "❌ La base restaurée contient $ROWS lignes ; la vivante en a $LIVE_ROWS." >&2
        echo "   Attendu au moins $MIN_ROWS. La sauvegarde est INCOMPLÈTE." >&2
        exit 1
    fi
fi

echo "✅ Restore drill OK — $TABLES tables (vivant : $LIVE_TABLES), $ROWS lignes (vivant : $LIVE_ROWS)."
