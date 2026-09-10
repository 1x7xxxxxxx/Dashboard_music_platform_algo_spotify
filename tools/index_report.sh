#!/usr/bin/env bash
# Les index jamais parcourus — avec ce qu'il faut pour DÉCIDER, pas pour obéir.
#
# Sépare trois populations que « 232 index inutilisés » confond :
#   1. ceux qui servent une contrainte (PK/unique) — ils ne sont pas là pour lire,
#      ils rendent un doublon impossible. On ne les propose JAMAIS ;
#   2. ceux dont un autre index couvre déjà les colonnes en préfixe — démontrablement
#      inutiles, retirés par la migration 099 ;
#   3. le reste : jamais lus, mais rien ne prouve qu'ils soient inutiles. C'est ce que
#      ce rapport liste, avec leur DDL de recréation, pour un arbitrage humain.
set -uo pipefail
PG_CONT="${PG_CONT:-$(docker ps --format '{{.Names}}' | grep '^postgres_spotify' | head -1)}"
[ -n "$PG_CONT" ] || { echo "❌ aucun conteneur postgres_spotify* en marche. Lancer : make up"; exit 1; }
DB="${DB_NAME:-spotify_etl}"
SU="${DB_USER:-$(docker exec "$PG_CONT" sh -c 'echo $POSTGRES_USER')}"
q() { docker exec -i "$PG_CONT" psql -U "$SU" -d "$DB" -tAF' | ' -c "$1"; }

echo "── depuis quand ces compteurs courent"
q "SELECT COALESCE(stats_reset::text, 'jamais remis à zéro — les compteurs couvrent toute la vie de la base') FROM pg_stat_database WHERE datname = current_database()"
echo "   (un compteur remis à zéro récemment rendrait tous ces zéros ininterprétables)"

echo
echo "── les populations"
q "SELECT
     'total'||' : '||count(*)||' index, '||pg_size_pretty(sum(pg_relation_size(s.indexrelid)))
   FROM pg_stat_user_indexes s"
q "SELECT
     'jamais parcourus mais garants d une contrainte (INTOUCHABLES) : '
     ||count(*)||', '||pg_size_pretty(COALESCE(sum(pg_relation_size(s.indexrelid)),0))
   FROM pg_stat_user_indexes s JOIN pg_index i ON i.indexrelid = s.indexrelid
   WHERE s.idx_scan = 0 AND (i.indisunique OR i.indisprimary)"
q "SELECT
     'jamais parcourus, sans contrainte (à ARBITRER) : '
     ||count(*)||', '||pg_size_pretty(COALESCE(sum(pg_relation_size(s.indexrelid)),0))
   FROM pg_stat_user_indexes s JOIN pg_index i ON i.indexrelid = s.indexrelid
   WHERE s.idx_scan = 0 AND NOT i.indisunique AND NOT i.indisprimary"

echo
echo "── à arbitrer, du plus lourd au plus léger (table | index | poids | DDL de recréation)"
q "SELECT s.relname, s.indexrelname, pg_size_pretty(pg_relation_size(s.indexrelid)),
          pg_get_indexdef(s.indexrelid)
   FROM pg_stat_user_indexes s JOIN pg_index i ON i.indexrelid = s.indexrelid
   WHERE s.idx_scan = 0 AND NOT i.indisunique AND NOT i.indisprimary
   ORDER BY pg_relation_size(s.indexrelid) DESC, s.relname
   LIMIT ${LIMIT:-25}"

echo
echo "Retirer un index est réversible : le DDL ci-dessus le recrée à l'identique."
echo "Ce que le retrait gagne n'est pas l'espace, c'est le travail d'écriture évité"
echo "à chaque upsert nocturne sur ces tables."
