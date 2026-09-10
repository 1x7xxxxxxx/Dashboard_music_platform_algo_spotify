#!/usr/bin/env bash
# Le rôle applicatif : poser son mot de passe, puis PROUVER ses bornes.
#
# La logique vit ici et pas dans le Makefile pour la raison de `migrate.sh` : `make`
# n'est pas installé sur le serveur de production, donc une recette qui ne marche que
# par `make` ne marche pas là où elle compte.
#
# Deux modes :
#   set    APP_DB_PASSWORD=… bash tools/db_app_role.sh set
#   check  bash tools/db_app_role.sh check     — n'écrit rien, sort ≠ 0 si une borne cède
set -uo pipefail

MODE="${1:-check}"
DB="${DB_NAME:-spotify_etl}"
# Le MÊME ancrage que `tools/migrate.sh` : `grep postgres` tout court attrape le
# conteneur d'un AUTRE projet de cette machine, et la commande part alors sur une base
# qui n'a rien à voir. Mesuré ici même le 2026-09-10.
PG_CONT="${PG_CONT:-$(docker ps --format '{{.Names}}' | grep '^postgres_spotify' | head -1)}"
[ -n "$PG_CONT" ] || { echo "❌ aucun conteneur postgres_spotify* en marche. Lancer : make up"; exit 1; }
SU="${DB_USER:-$(docker exec "$PG_CONT" sh -c 'echo $POSTGRES_USER')}"
[ -n "$SU" ] || { echo "❌ impossible de lire POSTGRES_USER dans $PG_CONT"; exit 1; }

psql_su() { docker exec -i "$PG_CONT" psql -U "$SU" -d "$DB" "$@"; }

if [ "$MODE" = "set" ]; then
    [ -n "${APP_DB_PASSWORD:-}" ] || {
        echo "❌ APP_DB_PASSWORD non posé."
        echo "   APP_DB_PASSWORD='…' bash tools/db_app_role.sh set"; exit 1; }
    # Le mot de passe passe par un paramètre de session, jamais par la ligne de
    # commande d'un conteneur (elle est lisible dans `docker inspect` et l'historique).
    printf "SET app.streamlytics_app_password = %s;\n" \
           "$(printf '%s' "$APP_DB_PASSWORD" | sed "s/'/''/g; s/^/'/; s/$/'/")" \
        | cat - migrations/098_the_app_is_not_a_superuser.sql | psql_su -q -v ON_ERROR_STOP=1 \
        || { echo "❌ la pose du mot de passe a échoué"; exit 1; }
    echo "✅ mot de passe posé sur streamlytics_app."
    echo "   Basculer l'app : DATABASE_USER=streamlytics_app + DATABASE_PASSWORD=<le même>, puis redémarrer."
    exit 0
fi

fail=0
say() { printf '  %-52s %s\n' "$1" "$2"; }

echo "── attributs du rôle"
# Un seul booléen, pas quatre : `-tA` rend `t`/`f` sur certaines versions et
# `true`/`false` sur d'autres, et comparer la CHAÎNE fait échouer un contrôle correct.
attrs=$(psql_su -tAc "SELECT NOT (rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls) FROM pg_roles WHERE rolname='streamlytics_app'" 2>/dev/null | tr -d '\r ')
if [ -z "$attrs" ]; then
    echo "❌ le rôle streamlytics_app n'existe pas. Lancer : make migrate"; exit 1
fi
case "$attrs" in
    t|true) say "NOSUPERUSER/NOCREATEDB/NOCREATEROLE/NOBYPASSRLS" "✅" ;;
    *)      say "le rôle porte un attribut de privilège (lu '$attrs')" "❌"; fail=1 ;;
esac

member=$(psql_su -tAc "SELECT count(*) FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.roleid JOIN pg_roles u ON u.oid=m.member WHERE u.rolname='streamlytics_app' AND r.rolname IN ('pg_execute_server_program','pg_read_server_files','pg_write_server_files')" | tr -d '\r ')
if [ "$member" = "0" ]; then say "hors des rôles d'accès à l'hôte" "✅"
else say "membre de $member rôle(s) d'accès à l'hôte" "❌"; fail=1; fi

echo "── les droits sur les données"
tables=$(psql_su -tAc "SELECT count(*) FROM pg_tables t WHERE t.schemaname='public' AND NOT has_table_privilege('streamlytics_app', format('%I.%I', t.schemaname, t.tablename), 'SELECT')" | tr -d '\r ')
if [ "$tables" = "0" ]; then say "lit toutes les tables de public" "✅"
else say "$tables table(s) illisibles par l'app" "❌"; fail=1; fi

nowrite=$(psql_su -tAc "SELECT count(*) FROM pg_tables t WHERE t.schemaname='public' AND NOT has_table_privilege('streamlytics_app', format('%I.%I', t.schemaname, t.tablename), 'INSERT')" | tr -d '\r ')
if [ "$nowrite" = "0" ]; then say "écrit dans toutes les tables de public" "✅"
else say "$nowrite table(s) non inscriptibles par l'app" "❌"; fail=1; fi

echo "── ce qu'il ne doit PAS pouvoir"
for probe in "pg_authid:has_table_privilege('streamlytics_app','pg_authid','SELECT')" \
             "DDL dans public:has_schema_privilege('streamlytics_app','public','CREATE')"; do
    label="${probe%%:*}"; expr="${probe#*:}"
    got=$(psql_su -tAc "SELECT $expr" | tr -d '\r ')
    case "$got" in f|false) say "$label refusé" "✅" ;; *)
    say "$label ACCORDÉ" "❌"; fail=1 ;; esac
done

echo "── ce que l'app utilise aujourd'hui"
say "DATABASE_USER = ${DATABASE_USER:-postgres}" \
    "$([ "${DATABASE_USER:-postgres}" = "postgres" ] && echo '⚠️  superutilisateur' || echo '✅')"

[ "$fail" = "0" ] && echo "✅ le rôle applicatif tient ses bornes" || echo "❌ une borne a cédé"
exit "$fail"
