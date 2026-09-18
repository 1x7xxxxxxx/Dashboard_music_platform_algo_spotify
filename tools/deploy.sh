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
# ── Le REGISTRE des services deployables, et sa sonde (2026-09-16) ──────────
# Une seule liste, lue par la porte de sante ET par le rollback. Avant, la porte
# portait un `case` dont la branche par defaut etait `*) continue` : un service
# demande mais inconnu du `case` traversait le deploiement SANS AUCUNE
# VERIFICATION et sortait en 0. Le jour ou une seconde replique `dashboard2`
# arrive (R114), c'est exactement ce qui se serait passe — deployee, jamais
# sondee, jamais couverte par un retour arriere, en silence.
#
# Ajouter une replique = ajouter UNE ligne ici. Demander un service absent de ce
# registre est desormais une ERREUR, pas un silence.
service_probe() {
    case "$1" in
        api)        echo "http://127.0.0.1:8502/health" ;;
        dashboard)  echo "http://127.0.0.1:8501/_stcore/health" ;;
        dashboard2) echo "http://127.0.0.1:8511/_stcore/health" ;;
        *)          echo "" ;;
    esac
}

SERVICES="${*:-api dashboard}"

for s in $SERVICES; do
    if [ -z "$(service_probe "$s")" ]; then
        echo "STOP : le service '$s' n'a pas de sonde de sante dans ce script."
        echo "   Le deployer serait le mettre en service SANS verification et SANS"
        echo "   retour arriere. Ajouter sa sonde dans service_probe(), ou corriger"
        # Derive du registre, jamais reecrit : la liste ecrite a la main aurait
        # menti au premier service ajoute a `service_probe()` — et c'est
        # precisement ce message qu'on lit quand on vient d'en ajouter un.
        echo "   le nom. Services connus : $(sed -n '/^service_probe()/,/^}/p' "$0" \
            | sed -n 's/^ *\([a-z0-9_]*\)) *echo.*/\1/p' | tr '\n' ' ')"
        exit 1
    fi
done

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

# ── Les migrations en attente, verifiees AVANT de construire (2026-09-16) ────
# L'ordre `migrate.sh` puis `deploy.sh` n'etait ecrit que dans une archive de roadmap.
# Quand il est inverse, rien n'echoue bruyamment : l'application DEMARRE, repond 200
# sur `/health`, et rend 500 sur les donnees. La porte de sante ne teste que la
# vivacite — la classe a deja coute un `/kpis` casse en production, vu le lendemain.
#
# On ne LANCE pas les migrations ici, a dessein : `tools/migrate.sh` ne pose pas
# `ON_ERROR_STOP` parce que le jeu n'est idempotent qu'en execution complete, et un
# deploiement n'est pas le bon endroit pour decider de ce compromis. On REFUSE, et on
# nomme la commande.
# On compare des ENSEMBLES, pas des cardinalites — corrige le 2026-09-16, le jour
# ou la version comptante a ete prise en flagrant delit de silence. Le depot portait
# 119 fichiers et la base 119 lignes, donc la porte etait verte ; et pourtant
# `106_gold_remaining_grains.sql` n'etait PAS enregistree (elle echouait a chaque
# rejeu sur `cannot drop columns from view`), sa ligne etant occupee au compte par
# `create_missing_tables.sql`. Deux erreurs qui s'annulent donnent un total juste et
# un verdict faux. Une porte qui compte ne peut pas nommer ce qui manque.
PG_CONT="${PG_CONT:-postgres_spotify_airflow}"
if docker ps --format '{{.Names}}' | grep -qx "$PG_CONT"; then
    ledger="$(docker exec -i "$PG_CONT" psql -U postgres -d spotify_etl -tA \
                -c "SELECT filename FROM schema_migrations;" 2>/dev/null || echo "")"
    if [ -n "$ledger" ]; then
        onrepo="$(ls migrations/*.sql 2>/dev/null | xargs -n1 basename | sort)"
        pending="$(comm -23 <(echo "$onrepo") <(echo "$ledger" | sort))"
        if [ -n "$pending" ]; then
            echo "STOP : migration(s) presente(s) dans le depot et absente(s) du registre :"
            echo "$pending" | sed 's/^/      /'
            echo "   Deployer maintenant demarrerait une application qui repond 200 sur"
            echo "   /health et 500 sur les donnees. Lancer d'abord :"
            echo "      bash tools/migrate.sh"
            exit 1
        fi
        echo "  migrations : $(echo "$onrepo" | wc -l) au depot, toutes enregistrees"
    fi
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

# ── Le retour arriere, ajoute le 2026-09-16 ──────────────────────────────────
# Jusqu'ici, une porte de sante rouge sortait en `exit 1` **en laissant le conteneur
# casse EN SERVICE**. `$before` etait capture ligne 19 et ne servait qu'a l'affichage
# ligne 22 : le script savait ou revenir, et n'y revenait pas.
#
# La seule manoeuvre de secours etait alors un revert et un second build de plusieurs
# minutes, a la main, sous trafic — c'est-a-dire au pire moment.
#
# Ce que ce retour arriere ne fait PAS, et qu'il faut savoir : il rend le CODE, jamais
# le SCHEMA. Une migration deja appliquee le reste. C'est pourquoi les migrations sont
# retro-compatibles par construction dans ce depot (ajout de colonne, jamais de
# suppression en vol) — et pourquoi `tools/migrate.sh` reste un geste separe, a lancer
# AVANT le deploiement.
rollback() {
    _svc="$1"; _url="$2"
    echo "RETOUR ARRIERE : $after -> $before (la porte de $_svc est rouge)"
    git reset --hard -q "$before" || { echo "   reset impossible — intervention manuelle"; return; }
    # Le service EN CAUSE, pas tout `$SERVICES` — corrige le 2026-09-16. La version
    # d'avant recevait `_svc` en argument et reconstruisait quand meme la liste
    # entiere : a deux repliques, l'echec de l'une aurait reconstruit les DEUX sous
    # trafic, donc coupe le site pour reparer une moitie. Reconstruire une seule
    # instance laisse l'autre servir pendant le retour.
    docker compose up -d --build "$_svc" >/dev/null 2>&1 \
        || { echo "   rebuild impossible — intervention manuelle"; return; }
    for _i in $(seq 1 30); do
        if curl -fsS -o /dev/null --max-time 5 "$_url" 2>/dev/null; then
            echo "   OK revenu sur $before, $_svc repond de nouveau"
            return
        fi
        sleep 1
    done
    echo "   $_svc ne repond TOUJOURS PAS apres le retour arriere."
    echo "      La panne ne vient donc pas du code deploye : regarder la base, le"
    echo "      reseau, ou l'hote. C'est une information, pas un echec du retour."
}

# Health gates: api on 8502/health, dashboard on 8501 Streamlit /_stcore/health.
for s in $SERVICES; do
    url="$(service_probe "$s")"
    printf "▶ waiting for %s health… " "$s"
    ok=""
    for i in $(seq 1 30); do
        if curl -fsS -o /dev/null --max-time 5 "$url" 2>/dev/null; then ok="${i}s"; break; fi
        sleep 1
    done
    if [ -z "$ok" ]; then
        echo "FAILED ($url did not return 200)"
        rollback "$s" "$url"
        exit 1
    fi
    echo "ok ($ok)"
done

echo "✅ deployed $after — $SERVICES healthy"
