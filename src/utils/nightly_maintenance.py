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
        # ⚠️ La rétention AVANT le résumé, et c'est délibéré : le résumé lit des fenêtres
        # de 24 h, donc purger d'abord ne lui retire rien, tandis que l'inverse ferait
        # payer au résumé le balayage d'une table qu'on s'apprête à rogner.
        #
        # L'échec est ISOLÉ comme celui de `purge_rate_limit_hits` ci-dessus : une
        # rétention qui tombe ne doit pas empêcher d'écrire le résumé, qui est la seule
        # série longue du dépôt. Mais il est JOURNALISÉ en `error`, pas avalé — une
        # purge muette est exactement le défaut que ce module vient de fermer.
        try:
            from src.utils.telemetry_retention import (
                purge_summary, purge_telemetry, undeclared_tables,
            )

            # ⚠️ Le CONTRÔLE avant la purge, pas après : une migration qui déclare une
            # rétention sans colonne d'âge doit se voir AVANT que la purge échoue
            # dessus. C'était la raison d'être d'`undeclared_tables`, et elle n'était
            # appelée par personne — trouvé le 2026-09-17 en balayant les fonctions
            # publiques sans appelant, sur un module écrit le jour même.
            manquantes = undeclared_tables(db)
            if manquantes:
                logger.error("rétention DÉCLARÉE sans colonne d'âge connue sur %s — "
                             "la purge les saute : %s", len(manquantes), manquantes)

            retention = purge_telemetry(db)
            # `purge_summary` rend la ligne lisible que ce module promet au mail du
            # soir. Elle non plus n'avait aucun appelant : le résumé partait en brut.
            logger.info("%s", purge_summary(retention))
        except Exception as exc:  # noqa: BLE001
            retention = None
            logger.error("rétention de télémétrie en échec (%s) — le résumé s'écrit "
                         "quand même", type(exc).__name__, exc_info=exc)

        from src.utils.daily_ops_metrics import write

        summary = write(db)
        if retention is not None:
            summary["retention"] = retention
            # La ligne LISIBLE à côté de la donnée brute : c'est elle que le mail du
            # soir affiche, et la garder hors du résumé la rendait inatteignable.
            from src.utils.telemetry_retention import purge_summary as _summary
            summary["retention_line"] = _summary(retention)
    finally:
        db.close()

    if not summary.get("complete"):
        # On NE lève PAS : une ligne incomplète est écrite à dessein, et faire échouer
        # la tâche ferait crier `tools/infra_health_cron.sh` pour une métrique absente.
        # Le champ `complete` porte l'information là où quelqu'un la lira.
        logger.warning("résumé quotidien INCOMPLET — Prometheus n'a pas tout rendu")
    return summary
