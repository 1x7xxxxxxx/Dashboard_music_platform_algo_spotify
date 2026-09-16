"""L'entretien de la nuit — purge et résumé, hors du DAG.

Type: Utility
Uses: src.utils.rate_limit_maintenance, src.utils.daily_ops_metrics
Triggers: la tâche `nightly_maintenance` d'`alert_monitor` (23 h UTC)
Persists in: rate_limit_hits (suppression), daily_ops_metrics (une ligne par jour)

Pourquoi ici et pas dans le DAG
--------------------------------
`airflow/dags/alert_monitor.py` porte un cliquet de longueur qui ne monte jamais, et il
est déjà le plus long fichier du dépôt à 2 700 lignes. Ce n'est pas une contrainte de
style : chaque sujet qu'on y ajoute est un sujet qu'on ne peut plus tester sans Airflow.
Le DAG garde l'horaire ; la logique vit ici, où elle s'appelle avec un simple import.

Pourquoi UNE tâche pour DEUX gestes
------------------------------------
Ils sont tous deux de l'entretien et ne remontent rien au mail consolidé. Les séparer
coûterait deux opérateurs dans un graphe qui en porte déjà vingt-deux, pour une
distinction que personne ne fait en lisant.

Mais ils sont INDÉPENDANTS dans leur exécution : le résumé s'écrit même si la purge a
échoué. Une purge ratée n'a aucune raison d'empêcher une mesure d'être conservée — c'est
exactement le genre de couplage qui fait perdre une journée d'historique pour une
broutille.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def run() -> dict:
    """Purge puis résumé. Rend le résumé écrit. Ne lève que si le résumé échoue."""
    from src.database.postgres_handler import PostgresHandler

    try:
        from src.utils.rate_limit_maintenance import purge_rate_limit_hits

        purge_rate_limit_hits()
    except Exception as exc:  # noqa: BLE001 — indépendant du résumé, voir le module
        logger.error("purge rate_limit_hits en échec (%s) — le résumé s'écrit quand "
                     "même", type(exc).__name__)

    db = PostgresHandler.from_env_or_config()
    try:
        from src.utils.daily_ops_metrics import write

        summary = write(db)
    finally:
        db.close()

    if not summary.get("complete"):
        # On NE lève PAS : une ligne incomplète est écrite à dessein, et faire échouer
        # la tâche ferait crier `tools/infra_health_cron.sh` pour une métrique absente.
        # Le champ `complete` porte l'information là où quelqu'un la lira.
        logger.warning("résumé quotidien INCOMPLET — Prometheus n'a pas tout rendu")
    return summary
