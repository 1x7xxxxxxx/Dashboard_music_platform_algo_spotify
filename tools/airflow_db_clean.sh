#!/usr/bin/env bash
# Purge de l'historique Airflow — `airflow db clean`, rétention paramétrable.
#
# Pourquoi ce script existe — mesuré le 2026-09-04.
#
# La base de métadonnées Airflow pesait **246 Mo**, soit près de SIX FOIS la base
# applicative qu'elle orchestre (43 Mo), avec 83 jours d'historique remontant au
# 2026-06-13 et jamais purgés :
#
#     task_instance  115 160 lignes  106 Mo
#     log            320 765 lignes   80 Mo
#     job             61 874 lignes   18 Mo
#     task_fail       55 762 lignes   14 Mo
#     dag_run         29 115 lignes   13 Mo
#
# Dont **98,4 % des task_instance** produits par les quatre `*_csv_watcher`, qui
# tournaient toutes les 15 minutes sur des répertoires vides.
#
# Ce que ça coûte de ne pas purger : la sauvegarde nocturne embarque tout, chaque
# requête du scheduler traverse davantage de lignes, et l'espace disque part en
# journal d'exécutions que personne ne relira.
#
# Usage:  tools/airflow_db_clean.sh [--dry-run]
# Env:    RETENTION_DAYS (défaut 30), AIRFLOW_CONT (auto)
set -euo pipefail

RETENTION_DAYS="${RETENTION_DAYS:-30}"
AIRFLOW_CONT="${AIRFLOW_CONT:-$(docker ps --format '{{.Names}}' | grep '^airflow_scheduler' | head -1)}"
DRY_RUN=""
[ "${1:-}" = "--dry-run" ] && DRY_RUN="--dry-run"

if [ -z "$AIRFLOW_CONT" ]; then
    echo "❌ Conteneur airflow_scheduler introuvable." >&2
    exit 1
fi

CUTOFF="$(date -u -d "-${RETENTION_DAYS} days" +%Y-%m-%d)"
echo "→ Purge de l'historique Airflow antérieur au ${CUTOFF} (rétention ${RETENTION_DAYS} j)"

# `--yes` parce que ce script tourne sous cron : une invite interactive y bloquerait
# indéfiniment sans que rien ne le signale — la classe `procedure-waits-for-a-human`.
docker exec "$AIRFLOW_CONT" airflow db clean \
    --clean-before-timestamp "${CUTOFF}" --yes --skip-archive $DRY_RUN

echo "✅ Purge terminée (rétention ${RETENTION_DAYS} j)."
