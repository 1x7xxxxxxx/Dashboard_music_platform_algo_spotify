"""Entretien de la table des compteurs de limitation.

Type: Utility
Uses: src.database.postgres_handler, src.dashboard.utils.throttle, src.api.security
Triggers: la tâche `purge_rate_limit_hits` d'`alert_monitor` (quotidienne)
Persists in: rate_limit_hits (suppression seulement)

Pourquoi ce module et pas dix lignes dans le DAG
------------------------------------------------
`airflow/dags/alert_monitor.py` porte un cliquet de longueur qui ne monte jamais
(`tests/test_a_file_only_gets_shorter.py`). Ce n'est pas une contrainte de style : un
fichier d'alerte de 2 700 lignes est déjà le plus long du dépôt, et chaque sujet qu'on
y ajoute est un sujet qu'on ne peut plus tester seul. La logique vit donc ici, où elle
s'appelle sans Airflow ; le DAG ne porte que son horaire.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Âge au-delà duquel une ligne est effacée. Les clés VIVANTES sont déjà nettoyées par
# `PostgresHitStore.hit()`, qui supprime les coups hors fenêtre de la clé qu'il touche.
# Ce qui reste ici, ce sont les clés ABANDONNÉES — une tentative unique depuis une IP
# qu'on ne reverra jamais garderait sa ligne pour toujours, et la cardinalité de cette
# table est pilotée par du trafic NON AUTHENTIFIÉ.
PURGE_AFTER_SECS = 86_400


def longest_window_secs() -> tuple[int, dict[str, int]]:
    """La plus longue fenêtre de limitation du produit, et le détail par seau."""
    from src.api import security
    from src.dashboard.utils import throttle

    windows = {
        "register": int(throttle.REGISTER_WINDOW_SECS),
        "totp": int(throttle.TOTP_WINDOW_SECS),
        "login": int(throttle.LOGIN_WINDOW_SECS),
        "api/auth": int(security.AUTH_RATE_LIMIT_WINDOW_SECS),
    }
    return max(windows.values()), windows


def purge_rate_limit_hits(db=None) -> int:
    """Efface les coups abandonnés. Rend le nombre de lignes supprimées.

    La marge sur la plus longue fenêtre est VÉRIFIÉE, pas affirmée dans une docstring.
    Les quatre fenêtres sont réglables par variable d'environnement ; en porter une
    au-delà d'un jour ferait de cette purge une remise à zéro nocturne des budgets —
    une porte ouverte chaque nuit, sans que rien ne le dise. Une purge qui ne peut pas
    prouver sa marge ne purge pas.
    """
    longest, windows = longest_window_secs()
    if longest >= PURGE_AFTER_SECS:
        raise ValueError(
            f"la plus longue fenêtre de limitation vaut {longest} s, la purge efface "
            f"au-delà de {PURGE_AFTER_SECS} s : elle tronquerait une fenêtre VIVANTE, "
            f"donc remettrait le budget à zéro chaque nuit. Fenêtres : {windows}"
        )

    owned = db is None
    if owned:
        from src.database.postgres_handler import PostgresHandler

        db = PostgresHandler.from_env_or_config()
    try:
        # `execute_query` puis `rowcount` — surtout pas `RETURNING 1` : matérialiser une
        # ligne Python par ligne effacée est sans borne, et c'est précisément la
        # cardinalité qu'on vient purger.
        db.execute_query(
            "DELETE FROM rate_limit_hits WHERE created_at < now() - interval '1 day'")
        deleted = int(db.cursor.rowcount or 0)
    finally:
        if owned:
            db.close()

    logger.info("purge rate_limit_hits : %d ligne(s), marge %d s sur la plus longue "
                "fenêtre (%d s)", deleted, PURGE_AFTER_SECS - longest, longest)
    return deleted
